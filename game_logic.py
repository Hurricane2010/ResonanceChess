import chess, random, copy, time, re, requests
from textblob import TextBlob
from piece_profile import PieceProfile
from utils import lichess_evaluate, ollama_say

# ------------------ CONFIGURATION ------------------
# Recognize both UCI and prefixed-UCI (like Ng1f4)
MOVE_RE = re.compile(r"^[NBRQK]?[a-h][1-8][a-h][1-8][qrbn]?$", re.IGNORECASE)

# Thresholds for supernatural behavior
HEROIC_BELIEF_THRESHOLD = 95.0   # Fully illegal "reality-bending" moves
PSEUDO_BELIEF_THRESHOLD = 85.0   # Pseudo-legal (e.g., moving into check)
HEROIC_OVERRIDE_MORALE = 30      # Minimum army morale before collapse
# ---------------------------------------------------


class CharismaChess:
    """Handles chess logic, emotional system, and anime-style leadership behavior."""

    def __init__(self):
        self.board = chess.Board()
        self.piece_profiles = self._initialize_profiles_once()
        self.last_speech_time = 0
        self.speech_decay_factor = 1.0
        self.speech_counter = 0

    # ---------------- Initialization ----------------
    def _initialize_profiles_once(self):
        profiles = {}
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if p:
                profiles[sq] = PieceProfile(sq, p.color)
        return profiles

    # ---------------- Move mapping (profiles) ----------------
    def _rook_castle_squares(self, move):
        castles = {
            (chess.E1, chess.G1): (chess.H1, chess.F1),
            (chess.E1, chess.C1): (chess.A1, chess.D1),
            (chess.E8, chess.G8): (chess.H8, chess.F8),
            (chess.E8, chess.C8): (chess.A8, chess.D8),
        }
        return castles.get((move.from_square, move.to_square), (None, None))

    def _en_passant_capture_square(self, move, mover_color):
        if self.board.is_en_passant(move):
            return move.to_square - 8 if mover_color == chess.WHITE else move.to_square + 8
        return None

    def apply_move_profiles(self, move, mover_color):
        """Remap emotion profiles to new squares WITHOUT re-randomizing."""
        from_sq, to_sq = move.from_square, move.to_square
        if self.board.piece_at(to_sq) and self.board.piece_at(to_sq).color != mover_color:
            self.piece_profiles.pop(to_sq, None)
        ep_sq = self._en_passant_capture_square(move, mover_color)
        if ep_sq is not None:
            self.piece_profiles.pop(ep_sq, None)
        mover_prof = self.piece_profiles.pop(from_sq, None)
        if mover_prof:
            mover_prof.square = to_sq
            self.piece_profiles[to_sq] = mover_prof
        r_from, r_to = self._rook_castle_squares(move)
        if r_from is not None and r_to is not None:
            rook_prof = self.piece_profiles.pop(r_from, None)
            if rook_prof:
                rook_prof.square = r_to
                self.piece_profiles[r_to] = rook_prof

    # ---------------- Emotion system ----------------
    def get_team_average(self, color, attr):
        vals = [getattr(p, attr) for p in self.piece_profiles.values() if p.color == color]
        return sum(vals) / len(vals) if vals else 0

    def adjust_emotions(self, move_score, color):
        delta = move_score / 350.0
        for p in self.piece_profiles.values():
            if p.color == color:
                p.trust = max(0, min(100, p.trust + delta * 3.5))
                p.morale = max(0, min(100, p.morale + delta * 2.5))
                p.motivation = max(0, min(100, p.motivation + delta * 1.8))

    # ---------------- Speech system ----------------
    def _ollama_piece_reply(self, piece_name, square_name, attrs, player_text):
        sys = ("You are the inner voice of a chess piece in a dramatic war for morale. "
               "Respond briefly (max 20 words) with emotion and humanity.")
        mood = f"(morale {attrs['morale']:.0f}, trust {attrs['trust']:.0f}, loyalty {attrs['loyalty']:.0f}, motivation {attrs['motivation']:.0f})"
        user = f"You are the {piece_name} on {square_name.upper()} {mood}. Commander says: \"{player_text}\""
        return ollama_say(sys, user)

    def analyze_speech(self, text, color):
        sentiment = TextBlob(text).sentiment.polarity
        words = text.lower().split()
        now = time.time()
        # decay factor to avoid spam buffs
        self.speech_decay_factor *= 0.8 if now - self.last_speech_time < 8 else 1.05
        self.speech_decay_factor = min(1.0, self.speech_decay_factor)
        self.last_speech_time = now
        self.speech_counter += 1

        target_tag = next((w for w in words if w.startswith("@")), "@army")
        army_morale = self.get_team_average(color, "morale")
        desperation = max(0.35, (100 - army_morale) / 100)
        intensity = abs(sentiment * 12) * desperation * self.speech_decay_factor

        return (self._rally_army if target_tag in ["@army", "@all", "@troops"]
                else self._directed_speech)(target_tag, sentiment, intensity, color)

    def _rally_army(self, sentiment, intensity, color):
        for p in self.piece_profiles.values():
            if p.color == color:
                change = sentiment * intensity * random.uniform(6, 12)
                p.morale = max(0, min(100, p.morale + change))
                p.trust = max(0, min(100, p.trust + change * 0.6))
                p.motivation = max(0, min(100, p.motivation + change * 0.45))
        avg_morale = self.get_team_average(color, "morale")
        attrs = {
            "morale": avg_morale,
            "trust": self.get_team_average(color, "trust"),
            "loyalty": self.get_team_average(color, "loyalty"),
            "motivation": self.get_team_average(color, "motivation"),
        }
        return self._ollama_piece_reply("army", "ranks", attrs, text="Your speech echoes across the battlefield.")

    def _directed_speech(self, tag, sentiment, intensity, color):
        tag = tag.replace("@", "").lower()
        for sq, prof in self.piece_profiles.items():
            piece = self.board.piece_at(sq)
            if not piece or piece.color != color:
                continue
            symbol = piece.symbol().lower()
            square = chess.square_name(sq)
            combos = {square, f"{square}{symbol}", f"{symbol}{square}", symbol}
            if tag in combos:
                change = sentiment * intensity * random.uniform(8, 15)
                prof.morale = max(0, min(100, prof.morale + change))
                prof.trust = max(0, min(100, prof.trust + change * 0.85))
                prof.motivation = max(0, min(100, prof.motivation + change * 0.65))
                attrs = {
                    "morale": prof.morale,
                    "trust": prof.trust,
                    "loyalty": prof.loyalty,
                    "motivation": prof.motivation,
                }
                name = {"p": "pawn", "n": "knight", "b": "bishop",
                        "r": "rook", "q": "queen", "k": "king"}[symbol]
                return self._ollama_piece_reply(name, square, attrs, player_text=tag)
        return f"Your voice echoes in vain — no @{tag} listens."

    # ---------------- Helpers ----------------
    def _team_belief(self, color):
        return 0.6 * self.get_team_average(color, "trust") + 0.4 * self.get_team_average(color, "morale")

    def _extract_move_token(self, text):
        """Extract UCI-like or prefixed-UCI token (e.g. 'Ng1f4' → 'g1f4')."""
        parts = text.strip().split()
        for tok in parts[::-1]:
            if MOVE_RE.match(tok):
                return tok[-4:].lower()
        return None

    def _parse_move_from_text(self, text):
        """Parse SAN, UCI, or '@tag <uci>' formatted move."""
        t = text.strip()
        uci_tok = self._extract_move_token(t)
        if uci_tok:
            try:
                return chess.Move.from_uci(uci_tok), True
            except ValueError:
                pass
        try:
            return self.board.parse_san(t), False
        except ValueError:
            try:
                return self.board.parse_uci(t), True
            except ValueError:
                return None, False

    # ---------------- Fantasy move handler ----------------
    def _force_fantasy_move(self, move):
        from_sq, to_sq = move.from_square, move.to_square
        piece = self.board.piece_at(from_sq)
        if not piece:
            return False, "No piece at that source square."
        if piece.color != chess.WHITE:
            return False, "You can only command your own pieces."
        self.board.remove_piece_at(to_sq)
        self.board.set_piece_at(to_sq, piece)
        self.board.remove_piece_at(from_sq)
        self.board.turn = not self.board.turn
        return True, None

    # ---------------- Move Mechanics ----------------
    def is_move_safe(self, move):
        temp = copy.deepcopy(self.board)
        temp.push(move)
        return not temp.is_attacked_by(not self.board.turn, move.to_square)

    def make_move(self, text):
        """Processes any player input: SAN, UCI, or heroic fantasy moves."""

        # --- 1. Morale check ---
        morale_avg = self.get_team_average(chess.WHITE, "morale")
        if morale_avg < 35:
            return {"success": False, "morale_broken": True,
                    "message": "Your army is broken — no one follows your command."}

        # --- 2. Parse move from chat text ---
        move, from_uci = self._parse_move_from_text(text)
        if move is None:
            return {"success": False, "message": "Invalid move format."}

        prof = self.piece_profiles.get(move.from_square)
        piece_name = None
        if prof:
            piece_obj = self.board.piece_at(move.from_square)
            piece_name = {
                "p": "pawn", "n": "knight", "b": "bishop",
                "r": "rook", "q": "queen", "k": "king"
            }.get(piece_obj.symbol().lower(), "soldier")

        # --- 3. Possible hesitation (low trust/morale) ---
        if prof and (prof.trust < 35 or prof.morale < 30) and random.random() < 0.65:
            prof.trust = max(0, prof.trust - 3)
            prof.morale = max(0, prof.morale - 3)
            quote = self._ollama_piece_reply(
                piece_name or "unit",
                chess.square_name(move.from_square),
                {"morale": prof.morale, "trust": prof.trust,
                "loyalty": prof.loyalty, "motivation": prof.motivation},
                "I hesitate to obey such an order..."
            )
            return {"success": False, "hesitated": True,
                    "message": f"{quote}  (The {piece_name} refused your command.)"}

        # --- 4. Calculate belief thresholds ---
        team_belief = self._team_belief(chess.WHITE)
        allow_pseudo = team_belief >= PSEUDO_BELIEF_THRESHOLD
        allow_fantasy = team_belief >= HEROIC_BELIEF_THRESHOLD

        try:
            # ----------------------------------------------------------------------
            # LEGAL MOVE
            # ----------------------------------------------------------------------
            if move in self.board.legal_moves:
                if not self.is_move_safe(move) and random.random() < 0.70:
                    # unsafe move hesitates
                    for p in self.piece_profiles.values():
                        if p.color == chess.WHITE:
                            p.morale = max(0, p.morale - 4)
                            p.trust = max(0, p.trust - 2)
                    return {"success": False, "hesitated": True,
                            "message": "The piece hesitated — 'This feels like death, my lord…'"}

                # perform legal move
                self.apply_move_profiles(move, chess.WHITE)
                self.board.push(move)
                try:
                    san = self.board.san(self.board.peek())
                except Exception:
                    san = move.uci()

                score = lichess_evaluate(self.board.fen())
                self.adjust_emotions(score, chess.WHITE)

                # optional piece flavor
                if prof:
                    attrs = {"morale": prof.morale, "trust": prof.trust,
                            "loyalty": prof.loyalty, "motivation": prof.motivation}
                    quote = self._ollama_piece_reply(piece_name, chess.square_name(move.to_square),
                                                    attrs, "I have moved as commanded, my lord.")
                    return {"success": True, "message": f"{quote}  (Played {san}, eval {score} cp)"}

                return {"success": True, "message": f"White played {san} (eval {score} cp)"}

            # ----------------------------------------------------------------------
            # PSEUDO-LEGAL MOVE (into check, etc.)
            # ----------------------------------------------------------------------
            if allow_pseudo and move in self.board.pseudo_legal_moves:
                self.apply_move_profiles(move, chess.WHITE)
                self.board.push(move)
                san = move.uci()
                for p in self.piece_profiles.values():
                    if p.color == chess.WHITE:
                        p.motivation = min(100, p.motivation + 2)
                score = lichess_evaluate(self.board.fen())
                self.adjust_emotions(score, chess.WHITE)

                if prof:
                    attrs = {"morale": prof.morale, "trust": prof.trust,
                            "loyalty": prof.loyalty, "motivation": prof.motivation}
                    quote = self._ollama_piece_reply(piece_name, chess.square_name(move.to_square),
                                                    attrs, "I risked everything to obey.")
                    return {"success": True, "message": f"{quote}  (Defied odds with {san})"}

                return {"success": True, "message": f"White defied the odds with {san}"}

            # ----------------------------------------------------------------------
            # HEROIC MOVE SYSTEM (Individual + Armywide)
            # ----------------------------------------------------------------------
            if from_uci and MOVE_RE.match(text.strip().split()[-1]):
                piece_belief = (prof.trust + prof.morale) / 2 if prof else 0
                heroic_roll = random.random()

                # Individual hero attempt (60% chance if belief ≥ 90)
                if piece_belief >= 90 and heroic_roll < 0.6:
                    ok, err = self._force_fantasy_move(move)
                    if not ok:
                        return {"success": False, "message": err or "Could not perform heroic move."}
                    self.apply_move_profiles(move, chess.WHITE)
                    for p in self.piece_profiles.values():
                        if p.color == chess.WHITE:
                            p.morale = min(100, p.morale + 2)
                            p.trust = min(100, p.trust + 1)
                    if prof:
                        attrs = {"morale": prof.morale, "trust": prof.trust,
                                "loyalty": prof.loyalty, "motivation": prof.motivation}
                        quote = self._ollama_piece_reply(piece_name, chess.square_name(move.to_square),
                                                        attrs, "I defied fate itself for you, commander!")
                        return {"success": True, "message": f"{quote}  ({move.uci()})"}
                    return {"success": True, "message": f"A lone hero defied fate with {move.uci()}!"}

                # Armywide miracle (collective morale)
                if team_belief >= HEROIC_BELIEF_THRESHOLD:
                    ok, err = self._force_fantasy_move(move)
                    if not ok:
                        return {"success": False, "message": err or "Could not perform divine move."}
                    self.apply_move_profiles(move, chess.WHITE)
                    for p in self.piece_profiles.values():
                        if p.color == chess.WHITE:
                            p.morale = min(100, p.morale + 6)
                            p.trust = min(100, p.trust + 4)
                            p.motivation = min(100, p.motivation + 3)
                    quote = self._ollama_piece_reply(
                        "army", "ranks",
                        {"morale": morale_avg, "trust": self.get_team_average(chess.WHITE, 'trust'),
                        "loyalty": self.get_team_average(chess.WHITE, 'loyalty'),
                        "motivation": self.get_team_average(chess.WHITE, 'motivation')},
                        "Together we transcended reality itself!"
                    )
                    return {"success": True, "message": f"{quote}  (White bent reality with {move.uci()})"}

            # ----------------------------------------------------------------------
            # Otherwise illegal
            # ----------------------------------------------------------------------
            return {"success": False, "message": "Illegal move."}

        except Exception as e:
            # --- Recovery in case of unexpected failure ---
            print(f"[ERROR] Move processing failed: {e}")
            self.board.turn = chess.WHITE
            return {"success": False, "message": "System recovered from move error."}


    # ---------------- Enemy Reply ----------------
    def enemy_move(self, force_black=False):
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
        except Exception as e:
            legal = list(self.board.legal_moves)
            if not legal:
                if force_black:
                    self.board.turn = original_turn
                return "Black has no legal moves."
            move = random.choice(legal)
            tag = "(fallback)"
        else:
            tag = "(AI)"

        self.apply_move_profiles(move, chess.BLACK)
        self.board.push(move)
        if force_black:
            self.board.turn = chess.WHITE
        try:
            san = self.board.san(move)
        except Exception:
            san = move.uci()
        return f"Black played {san} {tag}"
