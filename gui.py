import tkinter as tk
import chess
from game_engine.game_logic import CharismaChess, EmotionSystem

class CharismaChessGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Charisma Chess — Modular + Fantasy Moves Edition")
        self.game = CharismaChess()

        # Help
        helpf = tk.Frame(master, width=180, bg="#2B2B2B")
        helpf.grid(row=0, column=0, rowspan=2, sticky="nswe")
        tk.Label(helpf, text="Move & Talk", bg="#2B2B2B", fg="white",
                 font=("Arial", 14, "bold")).pack(pady=(10, 0))
        tk.Label(helpf, text=(
            "Moves:\n  e4, Nf3, Qxe5\n"
            "UCI:\n  d2d4, e7e8q\n"
            "Tagged move:\n  @d2p d2d6 (orders pawn @d2)\n"
            "Talk:\n  @army 'Stand firm!'\n  @c1b 'Hold the line.'\n"
            "Stats:\n  @e2pstats"
        ), font=("Consolas", 10), bg="#2B2B2B", fg="#DDD", justify="left").pack(padx=5, pady=5)

        # Board + chat
        self.canvas = tk.Canvas(master, width=480, height=480)
        self.canvas.grid(row=0, column=1)
        self.chat_log = tk.Text(master, width=40, height=20, bg="#222", fg="#EEE",
                                wrap=tk.WORD, state=tk.DISABLED)
        self.chat_log.grid(row=0, column=2, padx=10, pady=5)
        self.chat_entry = tk.Entry(master, width=35)
        self.chat_entry.grid(row=1, column=2, sticky="w", padx=10)
        tk.Button(master, text="Send", command=self.send_message).grid(row=1, column=2, sticky="e", padx=10)

        # Dashboard
        self.dashboard = tk.Canvas(master, width=660, height=80, bg="#111")
        self.dashboard.grid(row=2, column=0, columnspan=3, pady=5)
        self.update_board()
        self.update_dashboard()
        self.log_message("System", "Welcome, Commander.")

        # ---------------------------
        # ⚙️  Developer Testing Panel (Dev Only)
        # ---------------------------
        dev = tk.Frame(master, width=660, height=100, bg="#222")
        dev.grid(row=3, column=0, columnspan=3, pady=(10, 10))
        tk.Label(dev, text="⚙️  Testing Panel (Dev Only)", bg="#222", fg="#DDD",
                 font=("Consolas", 11, "bold")).grid(row=0, column=0, columnspan=6, pady=(5, 2))
        self.selected_piece_var = tk.StringVar(value="a2p")
        self.selected_attr_var = tk.StringVar(value="morale")
        self.new_value_var = tk.StringVar(value="100")
        tk.Label(dev, text="Piece Tag:", bg="#222", fg="#DDD").grid(row=1, column=0, sticky="e")
        tk.Entry(dev, textvariable=self.selected_piece_var, width=10).grid(row=1, column=1, sticky="w")
        tk.Label(dev, text="Attr:", bg="#222", fg="#DDD").grid(row=1, column=2, sticky="e")
        tk.OptionMenu(dev, self.selected_attr_var, "morale", "trust", "loyalty", "motivation", "empathy").grid(row=1, column=3, sticky="w")
        tk.Label(dev, text="Value:", bg="#222", fg="#DDD").grid(row=1, column=4, sticky="e")
        tk.Entry(dev, textvariable=self.new_value_var, width=6).grid(row=1, column=5, sticky="w")
        tk.Button(dev, text="Apply Piece", command=self.apply_piece_value).grid(row=2, column=1, pady=4)
        tk.Button(dev, text="Apply Army", command=self.apply_army_value).grid(row=2, column=3, pady=4)

    # ---- Core GUI Methods ----
    def update_board(self):
        self.canvas.delete("all")
        LIGHT, DARK = "#EEEED2", "#769656"
        PIECES = {'r': '♜','n': '♞','b': '♝','q': '♛','k': '♚','p': '♟',
                  'R': '♖','N': '♘','B': '♗','Q': '♕','K': '♔','P': '♙'}
        for row in range(8):
            for col in range(8):
                x1, y1 = col*60, row*60
                color = LIGHT if (row+col)%2==0 else DARK
                self.canvas.create_rectangle(x1,y1,x1+60,y1+60,fill=color)
                sq = chess.square(col,7-row)
                p = self.game.board.piece_at(sq)
                if p: self.canvas.create_text(x1+30,y1+30,text=PIECES[p.symbol()],font=("Arial",32))

    def log_message(self, sender, msg):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, f"{sender}: {msg}\n")
        self.chat_log.see(tk.END)
        self.chat_log.config(state=tk.DISABLED)

    def update_dashboard(self):
        g = self.game
        self.dashboard.delete("all")
        morale = g.emotions.get_team_average(chess.WHITE, "morale")
        trust  = g.emotions.get_team_average(chess.WHITE, "trust")
        motivation = g.emotions.get_team_average(chess.WHITE, "motivation")
        loyalty    = g.emotions.get_team_average(chess.WHITE, "loyalty")

        # Color/status
        if morale > 85 and trust > 75: label, col = "Inspired", "#4CAF50"
        elif morale > 65:              label, col = "Steady",   "#FFEB3B"
        elif morale > 45:              label, col = "Doubtful", "#FFA726"
        else:                          label, col = "Fearful",  "#E53935"

        self.dashboard.create_text(330, 15, text=f"ARMY STATUS: {label}", fill=col, font=("Consolas", 14, "bold"))
        self.dashboard.create_rectangle(100, 30, 100 + morale*4, 50, fill=col)
        self.dashboard.create_text(500, 40, text=f"Morale: {morale:.1f}", fill="white", font=("Consolas", 11))
        self.dashboard.create_text(330, 65,
            text=f"Trust: {trust:.1f}   Motivation: {motivation:.1f}   Loyalty: {loyalty:.1f}",
            fill="#DDD", font=("Consolas", 11))

    def _show_piece_stats(self, text):
        tag = text.strip().lower()
        if tag.startswith("@"): tag = tag[1:]
        if tag.endswith("stats"): tag = tag[:-5]
        tag = tag.strip()

        for sq, prof in self.game.piece_profiles.items():
            piece = self.game.board.piece_at(sq)
            if not piece or piece.color != chess.WHITE: continue
            s = chess.square_name(sq)
            sym = piece.symbol().lower()
            if tag in [s, f"{s}{sym}", f"{sym}{s}", sym]:
                self.log_message("Stats",
                    f"{piece.symbol().upper()} on {s.upper()}:\n"
                    f" Morale {prof.morale:.1f} | Trust {prof.trust:.1f}\n"
                    f" Loyalty {prof.loyalty:.1f} | Motivation {prof.motivation:.1f}\n"
                    f" Empathy {prof.empathy:.1f}")
                return
        self.log_message("System","No such piece found.")

    def send_message(self):
        t = self.chat_entry.get().strip()
        if not t: return
        self.chat_entry.delete(0, tk.END)

        # Stats requests: @e2pstats / @knightstats / @c1bstats etc.
        if t.lower().startswith("@") and t.lower().endswith("stats"):
            self._show_piece_stats(t)
            return

        # If line contains '@' but also ends with a UCI token -> treat as a tagged move
        # Otherwise, treat '@...' as speech.
        has_at = "@" in t
        looks_like_tagged_uci = has_at and bool(__import__("re").search(r"[a-h][1-8][a-h][1-8][qrbn]?$", t, __import__("re").IGNORECASE))

        if has_at and not looks_like_tagged_uci:
            r = self.game.analyze_speech(t, chess.WHITE)
            self.log_message("You", f"{t}\n→ {r}")
            self.update_dashboard()
            return

        # Try to make a move (SAN/UCI or @tag UCI)
        r = self.game.make_move(t)
        self.log_message("System", r.get("message", ""))
        self.update_board(); self.update_dashboard()

        if r.get("success"):
            self.update_board(); self.update_dashboard()
            reply = self.game.enemy_move()
            self.log_message("Black", reply)
            self.update_board(); self.update_dashboard()
        elif r.get("hesitated"):
            self.log_message("System", "Your hesitation gave the enemy an opening!")
            reply = self.game.enemy_move(force_black=True)
            self.log_message("Black", reply)
            self.update_board(); self.update_dashboard()

    # ---- Dev testing methods ----
    def apply_piece_value(self):
        tag = self.selected_piece_var.get().lower().replace("@", "")
        attr = self.selected_attr_var.get()
        try: val = float(self.new_value_var.get())
        except ValueError:
            self.log_message("System", "Invalid value."); return

        for sq, prof in self.game.piece_profiles.items():
            piece = self.game.board.piece_at(sq)
            if not piece or piece.color != chess.WHITE: continue
            s = chess.square_name(sq)
            sym = piece.symbol().lower()
            if tag in [s, f"{s}{sym}", f"{sym}{s}", sym]:
                setattr(prof, attr, max(0, min(100, val)))
                self.log_message("System", f"{attr.title()} of {piece.symbol().upper()}@{s.upper()} = {val:.1f}")
                self.update_dashboard()
                return
        self.log_message("System", "No piece found.")

    def apply_army_value(self):
        attr = self.selected_attr_var.get()
        try: val = float(self.new_value_var.get())
        except ValueError:
            self.log_message("System", "Invalid value."); return
        for prof in self.game.piece_profiles.values():
            if prof.color == chess.WHITE:
                setattr(prof, attr, max(0, min(100, val)))
        self.log_message("System", f"All army {attr.title()} set to {val:.1f}")
        self.update_dashboard()
