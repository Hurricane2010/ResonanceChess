import chess, copy, random, requests
from game_engine.config import MOVE_RE, HEROIC_BELIEF_THRESHOLD, PSEUDO_BELIEF_THRESHOLD
from utils import lichess_evaluate


class MoveEngine:
    """Handles all move parsing, legality, pseudo-legal, and fantasy ('heroic') rules."""

    def __init__(self, game_ref):
        self.game = game_ref
        self.board = game_ref.board
        self.piece_profiles = game_ref.piece_profiles

    # -------------------- Parsing helpers --------------------
    def _extract_move_token(self, text: str):
        """Find a UCI/prefixed-UCI token (e.g., 'Ng1f4' -> 'g1f4')."""
        for tok in text.strip().split()[::-1]:
            if MOVE_RE.match(tok):
                return tok[-4:].lower()
        return None

    def _parse_move_from_text(self, text: str):
        """Try SAN, UCI, or prefixed-UCI. If UCI is illegal, still return a dummy Move for fantasy path."""
        t = text.strip()
        uci_tok = self._extract_move_token(t)
        if uci_tok:
            try:
                return chess.Move.from_uci(uci_tok), True
            except ValueError:
                # construct dummy move so heroic path can still run
                try:
                    from_sq = chess.parse_square(uci_tok[:2])
                    to_sq = chess.parse_square(uci_tok[2:4])
                    return chess.Move(from_sq, to_sq), True
                except Exception:
                    return None, False
        # SAN
        try:
            return self.board.parse_san(t), False
        except ValueError:
            # raw UCI
            try:
                return self.board.parse_uci(t), True
            except ValueError:
                return None, False

    # -------------------- Fantasy move core --------------------
    def _force_fantasy_move(self, move: chess.Move):
        """Perform a truly illegal move by editing the board state directly."""
        from_sq, to_sq = move.from_square, move.to_square
        piece = self.board.piece_at(from_sq)
        if not piece:
            return False, "No piece at that source square."
        if piece.color != chess.WHITE:
            return False, "You can only command your own pieces."
        # capture whatever is on destination, then move
        self.board.remove_piece_at(to_sq)
        self.board.set_piece_at(to_sq, piece)
        self.board.remove_piece_at(from_sq)
        # flip turn like a normal move
        self.board.turn = not self.board.turn
        return True, None

    # -------------------- Safety --------------------
    def is_move_safe(self, move: chess.Move) -> bool:
        temp = copy.deepcopy(self.board)
        temp.push(move)
        # After push, it's opponent's turn; landed piece belongs to mover
        return not temp.is_attacked_by(not self.board.turn, move.to_square)

    # -------------------- Public API --------------------
    def make_move(self, text: str):
        """Processes any player input: SAN, UCI, pseudo-legal, or heroic fantasy moves."""
        # 1) Army morale gate
        morale_avg = self.game.emotions.get_team_average(chess.WHITE, "morale")
        if morale_avg < 35:
            return {"success": False, "morale_broken": True,
                    "message": "Your army is broken — no one follows your command."}

        # 2) Parse move
        move, from_uci = self._parse_move_from_text(text)
        if move is None:
            return {"success": False, "message": "Invalid move format."}

        # Profile and name of moving piece (if any presently on from_square)
        prof = self.piece_profiles.get(move.from_square)
        piece_name = None
        piece_obj = self.board.piece_at(move.from_square)
        if piece_obj:
            piece_name = {
                "p": "pawn", "n": "knight", "b": "bishop",
                "r": "rook", "q": "queen", "k": "king"
            }.get(piece_obj.symbol().lower(), "soldier")

        # 3) Possible hesitation for low trust/morale
        if prof and (prof.trust < 35 or prof.morale < 30) and random.random() < 0.65:
            prof.trust = max(0, prof.trust - 3)
            prof.morale = max(0, prof.morale - 3)
            quote = self.game.speech._ollama_reply(
                piece_name or "unit",
                chess.square_name(move.from_square),
                {"morale": prof.morale, "trust": prof.trust,
                 "loyalty": prof.loyalty, "motivation": prof.motivation},
                "I hesitate to obey such an order..."
            )
            return {"success": False, "hesitated": True,
                    "message": f"{quote}  (The {piece_name or 'unit'} refused your command.)"}

        # 4) Team belief thresholds
        team_belief = self.game.emotions.team_belief(chess.WHITE)
        allow_pseudo = team_belief >= PSEUDO_BELIEF_THRESHOLD
        allow_fantasy = team_belief >= HEROIC_BELIEF_THRESHOLD

        try:
            # ---------------- LEGAL ----------------
            if move in self.board.legal_moves:
                if not self.is_move_safe(move) and random.random() < 0.70:
                    # unsafe move -> hesitation + penalties
                    for p in self.piece_profiles.values():
                        if p.color == chess.WHITE:
                            p.morale = max(0, p.morale - 4)
                            p.trust = max(0, p.trust - 2)
                    return {"success": False, "hesitated": True,
                            "message": "The piece hesitated — 'This feels like death, my lord…'"}

                # perform move
                self.game.apply_move_profiles(move, chess.WHITE)
                self.board.push(move)
                try:
                    san = self.board.san(self.board.peek())
                except Exception:
                    san = move.uci()

                score = lichess_evaluate(self.board.fen())
                self.game.emotions.adjust_emotions(score, chess.WHITE)

                if prof and piece_name:
                    attrs = {"morale": prof.morale, "trust": prof.trust,
                             "loyalty": prof.loyalty, "motivation": prof.motivation}
                    quote = self.game.speech._ollama_reply(
                        piece_name, chess.square_name(move.to_square),
                        attrs, "I have moved as commanded, my lord."
                    )
                    return {"success": True, "message": f"{quote}  (Played {san}, eval {score} cp)"}

                return {"success": True, "message": f"White played {san} (eval {score} cp)"}

            # ---------------- PSEUDO-LEGAL (e.g., into check) ----------------
            if allow_pseudo and move in self.board.pseudo_legal_moves:
                self.game.apply_move_profiles(move, chess.WHITE)
                self.board.push(move)
                san = move.uci()

                # small motivation boost for bravery
                for p in self.piece_profiles.values():
                    if p.color == chess.WHITE:
                        p.motivation = min(100, p.motivation + 2)

                score = lichess_evaluate(self.board.fen())
                self.game.emotions.adjust_emotions(score, chess.WHITE)

                if prof and piece_name:
                    attrs = {"morale": prof.morale, "trust": prof.trust,
                             "loyalty": prof.loyalty, "motivation": prof.motivation}
                    quote = self.game.speech._ollama_reply(
                        piece_name, chess.square_name(move.to_square),
                        attrs, "I risked everything to obey."
                    )
                    return {"success": True, "message": f"{quote}  (Defied odds with {san})"}

                return {"success": True, "message": f"White defied the odds with {san}"}

            # ---------------- HEROIC (fantasy) ----------------
            if from_uci and MOVE_RE.match(text.strip().split()[-1]):
                # Individual belief
                piece_belief = (prof.trust + prof.morale) / 2 if prof else 0
                heroic_roll = random.random()

                # Individual hero (60% if belief ≥ 90)
                if piece_belief >= 90 and heroic_roll < 0.6:
                    ok, err = self._force_fantasy_move(move)
                    if not ok:
                        return {"success": False, "message": err or "Could not perform heroic move."}
                    self.game.apply_move_profiles(move, chess.WHITE)
                    for p in self.piece_profiles.values():
                        if p.color == chess.WHITE:
                            p.morale = min(100, p.morale + 2)
                            p.trust = min(100, p.trust + 1)
                    if prof and piece_name:
                        attrs = {"morale": prof.morale, "trust": prof.trust,
                                 "loyalty": prof.loyalty, "motivation": prof.motivation}
                        quote = self.game.speech._ollama_reply(
                            piece_name, chess.square_name(move.to_square),
                            attrs, "I defied fate itself for you, commander!"
                        )
                        return {"success": True, "message": f"{quote}  ({move.uci()})"}
                    return {"success": True, "message": f"A lone hero defied fate with {move.uci()}!"}

                # Armywide miracle
                if allow_fantasy:
                    ok, err = self._force_fantasy_move(move)
                    if not ok:
                        return {"success": False, "message": err or "Could not perform divine move."}
                    self.game.apply_move_profiles(move, chess.WHITE)
                    for p in self.piece_profiles.values():
                        if p.color == chess.WHITE:
                            p.morale = min(100, p.morale + 6)
                            p.trust = min(100, p.trust + 4)
                            p.motivation = min(100, p.motivation + 3)
                    quote = self.game.speech._ollama_reply(
                        "army", "ranks",
                        {"morale": self.game.emotions.get_team_average(chess.WHITE, "morale"),
                         "trust": self.game.emotions.get_team_average(chess.WHITE, "trust"),
                         "loyalty": self.game.emotions.get_team_average(chess.WHITE, "loyalty"),
                         "motivation": self.game.emotions.get_team_average(chess.WHITE, "motivation")},
                        "Together we transcended reality itself!"
                    )
                    return {"success": True, "message": f"{quote}  (White bent reality with {move.uci()})"}

            # Otherwise illegal
            return {"success": False, "message": "Illegal move."}

        except Exception as e:
            # Recovery on unexpected errors
            print(f"[ERROR] Move processing failed: {e}")
            self.board.turn = chess.WHITE
            return {"success": False, "message": "System recovered from move error."}

    def enemy_move(self, force_black: bool = False):
        """Get Black's move from Lichess cloud eval, or fallback to a random legal move."""
        if self.board.is_game_over():
            return "Game over."
        original_turn = self.board.turn
        if force_black and original_turn == chess.WHITE:
            self.board.turn = chess.BLACK

        try:
            r = requests.get("https://lichess.org/api/cloud-eval",
                             params={"fen": self.board.fen()}, timeout=3)
            data = r.json() if r.status_code == 200 else {}
            if "pvs" in data and data["pvs"]:
                mv = data["pvs"][0]["moves"].split(" ")[0]
                move = chess.Move.from_uci(mv)
            else:
                raise ValueError("No move suggestions found.")
        except Exception:
            # Fallback: random legal move
            legal = list(self.board.legal_moves)
            if not legal:
                if force_black:
                    self.board.turn = original_turn
                return "Black has no legal moves."
            move = random.choice(legal)
            tag = "(fallback)"
        else:
            tag = "(AI)"

        # Remap profiles BEFORE pushing
        self.game.apply_move_profiles(move, chess.BLACK)
        self.board.push(move)

        if force_black:
            self.board.turn = chess.WHITE

        try:
            san = self.board.san(move)
        except Exception:
            san = move.uci()
        return f"Black played {san} {tag}"
