import tkinter as tk
import chess
import random
import requests
from textblob import TextBlob
import copy
import time
import json

# -------------------------------
# Config
# -------------------------------
LICHESS_API_URL = "https://lichess.org/api/cloud-eval"
OLLAMA_URL = "http://localhost:11434/api/generate"   # Ollama local endpoint
OLLAMA_MODEL = "llama3.1"                             # change to your local model

# -------------------------------
# Emotional Profile for Each Piece
# -------------------------------
class PieceProfile:
    def __init__(self, square, color):
        self.square = square
        self.color = color
        self.loyalty = random.randint(60, 80)
        self.motivation = random.randint(60, 80)
        self.morale = random.randint(60, 80)
        self.trust = random.randint(50, 70)
        self.empathy = random.randint(40, 60)

    def average(self):
        return (self.loyalty + self.motivation + self.morale + self.trust + self.empathy) / 5


# -------------------------------
# Utilities: Lichess eval (cached)
# -------------------------------
_eval_cache = {}
def lichess_evaluate(fen):
    if fen in _eval_cache:
        return _eval_cache[fen]
    try:
        r = requests.get(LICHESS_API_URL, params={"fen": fen}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if "pvs" in data and data["pvs"]:
                cp = data["pvs"][0].get("cp", 0)
                _eval_cache[fen] = cp or 0
                return cp or 0
    except Exception:
        pass
    _eval_cache[fen] = 0
    return 0

# -------------------------------
# Utilities: Ollama text gen
# -------------------------------
def ollama_say(system_prompt, user_prompt, max_tokens=60, timeout=1.8):
    """
    Returns a short string from Ollama (or a safe fallback if unavailable).
    Kept short timeout so Tkinter stays responsive.
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\nUser: {user_prompt}\nAssistant:",
            "stream": False,
            "options": {"num_predict": max_tokens}
        }
        r = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=timeout, headers={"Content-Type":"application/json"})
        if r.status_code == 200:
            data = r.json()
            txt = data.get("response", "").strip()
            if txt:
                return txt
    except Exception:
        pass
    # Fallback
    return "…(the piece murmurs something under its breath, but you can sense its resolve shifting)…"


# -------------------------------
# Charisma Chess Core
# -------------------------------
class CharismaChess:
    def __init__(self):
        self.board = chess.Board()
        self.piece_profiles = self._initialize_profiles_once()
        self.last_speech_time = 0
        self.speech_decay_factor = 1.0
        self.speech_counter = 0

    def _initialize_profiles_once(self):
        profiles = {}
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if p:
                profiles[sq] = PieceProfile(sq, p.color)
        return profiles

    # ---------- Piece mapping utilities ----------
    def _rook_castle_squares(self, move):
        if move.from_square == chess.E1 and move.to_square == chess.G1:
            return (chess.H1, chess.F1)
        if move.from_square == chess.E1 and move.to_square == chess.C1:
            return (chess.A1, chess.D1)
        if move.from_square == chess.E8 and move.to_square == chess.G8:
            return (chess.H8, chess.F8)
        if move.from_square == chess.E8 and move.to_square == chess.C8:
            return (chess.A8, chess.D8)
        return (None, None)

    def _en_passant_capture_square(self, move, mover_color):
        if self.board.is_en_passant(move):
            if mover_color == chess.WHITE:
                return move.to_square - 8
            else:
                return move.to_square + 8
        return None

    def apply_move_profiles(self, move, mover_color):
        from_sq, to_sq = move.from_square, move.to_square
        # remove captured piece
        if self.board.piece_at(to_sq) and self.board.piece_at(to_sq).color != mover_color:
            self.piece_profiles.pop(to_sq, None)
        # en passant
        ep_sq = self._en_passant_capture_square(move, mover_color)
        if ep_sq is not None:
            self.piece_profiles.pop(ep_sq, None)
        # move mover profile
        mover_prof = self.piece_profiles.pop(from_sq, None)
        if mover_prof:
            mover_prof.square = to_sq
            self.piece_profiles[to_sq] = mover_prof
        # castle rook profile
        r_from, r_to = self._rook_castle_squares(move)
        if r_from is not None and r_to is not None:
            rook_prof = self.piece_profiles.pop(r_from, None)
            if rook_prof:
                rook_prof.square = r_to
                self.piece_profiles[r_to] = rook_prof

    # ---------- Team / eval / emotion ----------
    def get_team_average(self, color, attr):
        vals = [getattr(p, attr) for p in self.piece_profiles.values() if p.color == color]
        return sum(vals) / len(vals) if vals else 0

    def evaluate_position(self, board):
        return lichess_evaluate(board.fen())

    def adjust_emotions(self, move_score, color):
        # Slightly stronger swings
        delta = move_score / 350.0
        for p in self.piece_profiles.values():
            if p.color == color:
                p.trust = max(0, min(100, p.trust + delta * 3.5))
                p.morale = max(0, min(100, p.morale + delta * 2.5))
                p.motivation = max(0, min(100, p.motivation + delta * 1.8))

    # ---------- Speech mechanics ----------
    def analyze_speech(self, text, color):
        sentiment = TextBlob(text).sentiment.polarity
        words = text.lower().split()

        # Cooldown & diminishing returns
        now = time.time()
        if now - self.last_speech_time < 8:
            self.speech_decay_factor *= 0.8
        else:
            self.speech_decay_factor = min(1.0, self.speech_decay_factor + 0.12)
        self.last_speech_time = now
        self.speech_counter += 1

        target_tag = "@army"
        for w in words:
            if w.startswith("@"):
                target_tag = w
                break

        army_morale = self.get_team_average(color, "morale")
        desperation = max(0.35, (100 - army_morale) / 100)
        base_intensity = max(1.0, abs(sentiment * 12) * desperation * self.speech_decay_factor)

        if target_tag in ["@army", "@all", "@troops"]:
            reply = self._rally_army(sentiment, base_intensity, color)
        else:
            reply = self._directed_speech(target_tag, sentiment, base_intensity, color)
        return reply

    def _ollama_piece_reply(self, piece_name, square_name, attrs, player_text):
        sys = (
            "You are the inner voice of a chess piece in a dramatic strategy game. "
            "Speak in one short, human sentence (max ~20 words), reacting to your commander. "
            "Tone reflects your current state. Avoid emojis."
        )
        mood = f"(morale {attrs['morale']:.0f}, trust {attrs['trust']:.0f}, loyalty {attrs['loyalty']:.0f}, motivation {attrs['motivation']:.0f})"
        user = f"You are the {piece_name} on {square_name.upper()} {mood}. Commander says: \"{player_text}\". Reply briefly."
        return ollama_say(sys, user)

    def _rally_army(self, sentiment, intensity, color):
        # Heavier influence than before
        for p in self.piece_profiles.values():
            if p.color == color:
                change = sentiment * intensity * random.uniform(6, 12)
                p.morale = max(0, min(100, p.morale + change))
                p.trust = max(0, min(100, p.trust + change * 0.6))
                p.motivation = max(0, min(100, p.motivation + change * 0.45))
                # mild “overpromising” tax
                if self.speech_counter % 4 == 0:
                    p.trust = max(0, p.trust - 2)

        # Army “chorus” via Ollama (aggregate vibe)
        avg_morale = self.get_team_average(color, "morale")
        attrs = {"morale": avg_morale, "trust": self.get_team_average(color, "trust"),
                 "loyalty": self.get_team_average(color, "loyalty"),
                 "motivation": self.get_team_average(color, "motivation")}
        return self._ollama_piece_reply("army", "ranks", attrs, "Your speech to all troops")

    def _directed_speech(self, tag, sentiment, intensity, color):
        target_name = tag.replace("@", "").lower()

        piece_names = {'p': 'pawn','n': 'knight','b': 'bishop','r': 'rook','q': 'queen','k': 'king'}

        matched_sq, matched_piece = None, None
        for sq, prof in self.piece_profiles.items():
            piece = self.board.piece_at(sq)
            if not piece or piece.color != color:
                continue
            symbol = piece.symbol().lower()
            fullname = piece_names.get(symbol, symbol)
            square_name = chess.square_name(sq).lower()

            possible_tags = {
                square_name,
                fullname,
                f"{square_name}{fullname}",   # c4bishop
                f"{fullname}{square_name}",   # bishopc4
                f"{square_name}{symbol}",     # c4b
                f"{symbol}{square_name}",     # bc4
                f"{piece.symbol().upper()}{square_name}{fullname}",  # Bc4bishop
            }
            if target_name in possible_tags:
                matched_sq, matched_piece = sq, piece
                break

        if not matched_piece:
            return f"Your voice echoes in vain — no @{target_name} stands ready to listen."

        prof = self.piece_profiles[matched_sq]
        change = sentiment * intensity * random.uniform(8, 15)
        prof.morale = max(0, min(100, prof.morale + change))
        prof.trust = max(0, min(100, prof.trust + change * 0.85))
        prof.motivation = max(0, min(100, prof.motivation + change * 0.65))
        if self.speech_counter % 5 == 0:
            prof.trust = max(0, prof.trust - random.uniform(1, 4))

        attrs = {"morale": prof.morale, "trust": prof.trust, "loyalty": prof.loyalty, "motivation": prof.motivation}
        piece_name = piece_names.get(matched_piece.symbol().lower(), matched_piece.symbol().lower())
        return self._ollama_piece_reply(piece_name, chess.square_name(matched_sq), attrs, "A direct address from your commander")

    # ---------- Move logic with resistance/heroics ----------
    def is_move_safe(self, move):
        from_sq, to_sq = move.from_square, move.to_square
        piece = self.board.piece_at(from_sq)
        temp = copy.deepcopy(self.board)
        temp.push(move)
        return not temp.is_attacked_by(not piece.color, to_sq)

    def _piece_profile_for_move(self, move):
        prof = self.piece_profiles.get(move.from_square)
        return prof

    def _team_belief(self, color):
        # Aggregate trust+morale average
        return 0.6 * self.get_team_average(color, "trust") + 0.4 * self.get_team_average(color, "morale")

    def make_move(self, move_str):
        # Army collapse blocks commands
        morale_avg = self.get_team_average(chess.WHITE, "morale")
        if morale_avg < 35:
            return {"success": False, "morale_broken": True,
                    "message": "Your army is broken — no one follows your command."}

        # parse move (SAN first, then UCI)
        try:
            move = self.board.parse_san(move_str)
        except ValueError:
            try:
                move = self.board.parse_uci(move_str)
            except ValueError:
                return {"success": False, "message": "Invalid move format."}

        # Identify moving piece profile
        prof = self._piece_profile_for_move(move)

        # Resistance: very low trust/morale ≈ disobedience
        if prof and (prof.trust < 35 or prof.morale < 30):
            # chance to refuse even legal orders
            if random.random() < 0.65:
                # sting of disobedience
                prof.trust = max(0, prof.trust - 4)
                prof.morale = max(0, prof.morale - 3)
                prof.motivation = max(0, prof.motivation - 2)
                return {"success": False, "hesitated": True,
                        "message": "The unit refuses: 'I cannot… not like this.'"}
        
        # “Heroic rules”: if team belief is very high, allow pseudo-legal moves (ignore self-check)
        team_belief = self._team_belief(chess.WHITE)
        allow_pseudo = team_belief > 85

        # Legal / pseudo-legal gate
        is_legal = (move in self.board.legal_moves)
        is_pseudo = move in self.board.pseudo_legal_moves

        if not is_legal:
            if allow_pseudo and is_pseudo:
                # mark as heroic
                heroic = True
            else:
                return {"success": False, "message": "Illegal move."}
        else:
            heroic = False

        # Survival instinct check (reduced when trust high)
        safe = self.is_move_safe(move)
        if not heroic and not safe:
            # heightened trust reduces hesitation
            trust_factor = (prof.trust if prof else 50)
            hes_chance = 0.85 - (trust_factor / 200.0)  # 0.85->0.35 as trust grows 0->100
            if random.random() < hes_chance:
                # group sting
                for p in self.piece_profiles.values():
                    if p.color == chess.WHITE:
                        p.morale = max(0, p.morale - 5)
                        p.trust = max(0, p.trust - 3)
                        p.motivation = max(0, p.motivation - 2)
                return {"success": False, "hesitated": True,
                        "message": "The piece hesitated — 'This feels like death, my lord…'"}

        # Execute (profiles remapped before push)
        try:
            san_before = self.board.san(move) if is_legal else move.uci()
        except Exception:
            san_before = move.uci()

        self.apply_move_profiles(move, mover_color=chess.WHITE)
        self.board.push(move)

        # Evaluate & adjust (skip eval failures silently)
        score = self.evaluate_position(self.board)
        self.adjust_emotions(score, chess.WHITE)

        tag = " (heroic)" if heroic else ""
        return {"success": True, "message": f"White played {san_before}{tag} (eval {score} cp)"}

    def enemy_move(self, force_black=False):
        """Let Lichess play for Black. Falls back to a random legal move if eval fails."""
        if self.board.is_game_over():
            return "Game over."

        original_turn = self.board.turn
        if force_black and original_turn == chess.WHITE:
            self.board.turn = chess.BLACK

        try:
            resp = requests.get(LICHESS_API_URL, params={"fen": self.board.fen()}, timeout=3)
            if resp.status_code != 200:
                raise ValueError("Lichess returned non-200 status.")
            data = resp.json()
            if "pvs" in data and data["pvs"]:
                move_str = data["pvs"][0]["moves"].split(" ")[0]
                move = chess.Move.from_uci(move_str)
            else:
                raise ValueError("No move suggestions found.")
            msg = "(AI evaluated move)"
        except Exception as e:
            print(f"[WARN] AI move failed: {e}")
            legal_moves = list(self.board.legal_moves)
            if not legal_moves:
                if force_black:
                    self.board.turn = original_turn
                return "Black has no legal moves."
            move = random.choice(legal_moves)
            msg = "(fallback move)"

        try:
            san = self.board.san(move)
        except Exception:
            san = move.uci()

        self.apply_move_profiles(move, mover_color=chess.BLACK)
        self.board.push(move)

        if force_black:
            self.board.turn = chess.WHITE

        return f"Black played {san} {msg}"


# -------------------------------
# Tkinter GUI
# -------------------------------
class CharismaChessGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Charisma Chess — Ollama + Heroics Edition")
        self.game = CharismaChess()

        # Left help
        frame = tk.Frame(master, width=180, height=480, bg="#2B2B2B")
        frame.grid(row=0, column=0, rowspan=2, sticky="nswe")
        tk.Label(frame, text="Move & Talk Guide", font=("Arial", 14, "bold"),
                 bg="#2B2B2B", fg="white").pack(pady=(10, 0))
        tk.Label(
            frame,
            text=(
                "\nMoves:\n• e4, Nf3, Qxe5, O-O  |  UCI: e2e4\n\n"
                "Talk (Ollama replies):\n"
                "• @army  'Stand firm!'\n"
                "• @queen 'I trust you.'\n"
                "• @f3knight 'Guard the flank.'\n"
                "• @c4bishop 'Hold steady.'\n\n"
                "Stats:\n"
                "• @c4bstats, @e2pstats, @a1rstats\n"
            ),
            font=("Consolas", 10), bg="#2B2B2B", fg="#E0E0E0",
            justify="left", wraplength=160
        ).pack(padx=10, pady=5)

        # Board
        self.canvas = tk.Canvas(master, width=480, height=480)
        self.canvas.grid(row=0, column=1)

        # Chat
        self.chat_log = tk.Text(master, width=40, height=20, bg="#222", fg="#EEE", wrap=tk.WORD, state=tk.DISABLED)
        self.chat_log.grid(row=0, column=2, padx=10, pady=5)
        self.chat_entry = tk.Entry(master, width=35)
        self.chat_entry.grid(row=1, column=2, sticky="w", padx=10)
        self.chat_button = tk.Button(master, text="Send", command=self.send_message)
        self.chat_button.grid(row=1, column=2, sticky="e", padx=10)

        # Dashboard
        self.dashboard = tk.Canvas(master, width=660, height=80, bg="#111")
        self.dashboard.grid(row=2, column=0, columnspan=3, pady=5)

        self.update_board()
        self.update_dashboard()
        self.log_message("System", "Welcome, Commander. Inspire them — and they may break the rules for you.")
        
    def update_board(self):
        self.canvas.delete("all")
        LIGHT, DARK = "#EEEED2", "#769656"
        PIECES = {'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟',
                  'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔', 'P': '♙'}
        for row in range(8):
            for col in range(8):
                x1, y1 = col * 60, row * 60
                color = LIGHT if (row + col) % 2 == 0 else DARK
                self.canvas.create_rectangle(x1, y1, x1 + 60, y1 + 60, fill=color)
                sq = chess.square(col, 7 - row)
                p = self.game.board.piece_at(sq)
                if p:
                    self.canvas.create_text(x1 + 30, y1 + 30, text=PIECES[p.symbol()], font=("Arial", 32))

    def log_message(self, sender, msg):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, f"{sender}: {msg}\n")
        self.chat_log.see(tk.END)
        self.chat_log.config(state=tk.DISABLED)

    def update_dashboard(self, status_override=None):
        g = self.game
        self.dashboard.delete("all")
        morale = g.get_team_average(chess.WHITE, "morale")
        trust = g.get_team_average(chess.WHITE, "trust")
        motivation = g.get_team_average(chess.WHITE, "motivation")
        loyalty = g.get_team_average(chess.WHITE, "loyalty")

        if morale < 35:
            label, color = "BROKEN", "#B71C1C"
        elif status_override == "ENEMY_ADVANTAGE":
            label, color = "ENEMY ADVANTAGE", "#FF7043"
        elif morale > 85 and trust > 75:
            label, color = "Inspired", "#4CAF50"
        elif morale > 65:
            label, color = "Steady", "#FFEB3B"
        elif morale > 45:
            label, color = "Doubtful", "#FFA726"
        else:
            label, color = "Fearful", "#E53935"

        self.dashboard.create_text(330, 15, text=f"ARMY STATUS: {label}", fill=color, font=("Consolas", 14, "bold"))
        self.dashboard.create_rectangle(100, 30, 100 + morale * 4, 50, fill=color)
        self.dashboard.create_text(500, 40, text=f"Morale: {morale:.1f}", fill="white", font=("Arial", 12))
        stats = f"Trust: {trust:.1f}   Motivation: {motivation:.1f}   Loyalty: {loyalty:.1f}"
        self.dashboard.create_text(330, 65, text=stats, fill="#DDD", font=("Consolas", 11))

    def flash_enemy_advantage(self):
        self.update_dashboard(status_override="ENEMY_ADVANTAGE")
        self.master.after(1800, self.update_dashboard)

    def _handle_stats_query(self, text):
        # @<square><piece-initial>stats OR @<square>stats also accepted
        if not (text.lower().startswith("@") and text.lower().endswith("stats")):
            return False

        tag = text[1:-5].strip().lower()  # remove '@' and 'stats'
        if tag.endswith("'"):  # just in case quotes
            tag = tag[:-1]

        piece_found = None
        for sq, prof in self.game.piece_profiles.items():
            piece = self.game.board.piece_at(sq)
            if not piece or piece.color != chess.WHITE:
                continue
            square_name = chess.square_name(sq).lower()
            symbol = piece.symbol().lower()
            candidates = {square_name, f"{square_name}{symbol}", f"{symbol}{square_name}"}
            if tag in candidates:
                piece_found = (piece, prof, square_name)
                break

        if piece_found:
            piece, prof, sq = piece_found
            self.log_message("System", (
                f"📊 Stats for {piece.symbol().upper()} on {sq.upper()}:\n"
                f"• Morale: {prof.morale:.1f}\n"
                f"• Trust: {prof.trust:.1f}\n"
                f"• Loyalty: {prof.loyalty:.1f}\n"
                f"• Motivation: {prof.motivation:.1f}\n"
                f"• Empathy: {prof.empathy:.1f}"
            ))
        else:
            self.log_message("System", "No such piece found for that tag.")
        return True

    def _is_speech(self, text):
        tl = text.lower()
        return tl.startswith("@") or ("address" in tl) or ("talk to" in tl)

    def send_message(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, tk.END)

        # 0) Stats query
        if self._handle_stats_query(text):
            return

        # 1) Speech (Ollama reply path)
        if self._is_speech(text):
            response = self.game.analyze_speech(text, chess.WHITE)
            self.log_message("You", f"{text}\n→ {response}")
            self.update_dashboard()
            return

        # 2) Attempt move
        move_result = self.game.make_move(text)

        if move_result.get("success"):
            self.log_message("White", move_result["message"])
            self.update_board(); self.update_dashboard()
            reply = self.game.enemy_move()
            self.log_message("Black", reply)
            self.update_board(); self.update_dashboard()

        elif move_result.get("hesitated"):
            self.log_message("Army", move_result["message"])
            self.log_message("System", "Your hesitation gave the enemy an opening!")
            self.update_dashboard(); self.flash_enemy_advantage()
            reply = self.game.enemy_move(force_black=True)
            self.log_message("Black", reply)
            self.update_board(); self.update_dashboard()

        elif move_result.get("morale_broken"):
            self.log_message("Army", move_result["message"])
            self.update_dashboard()

        elif "Illegal" in move_result.get("message", "") or "Invalid" in move_result.get("message", ""):
            self.log_message("System", move_result["message"])
            self.update_dashboard()

        else:
            # If not recognized, treat as a general pep talk
            response = self.game.analyze_speech(text, chess.WHITE)
            self.log_message("You", f"{text}\n→ {response}")
            self.update_dashboard()

    def on_close(self):
        self.master.destroy()


# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = CharismaChessGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
