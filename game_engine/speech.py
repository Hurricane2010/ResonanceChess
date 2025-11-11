import random, time, chess
from textblob import TextBlob
from utils import ollama_say

class SpeechSystem:
    """Analyzes and applies morale boosts from commander dialogue."""

    def __init__(self, game_ref):
        self.game = game_ref
        self.last_speech_time = 0
        self.speech_decay_factor = 1.0
        self.speech_counter = 0

    def analyze_speech(self, text, color):
        sentiment = TextBlob(text).sentiment.polarity
        words = text.lower().split()
        now = time.time()
        self.speech_decay_factor *= 0.8 if now - self.last_speech_time < 8 else 1.05
        self.speech_decay_factor = min(1.0, self.speech_decay_factor)
        self.last_speech_time = now

        target_tag = next((w for w in words if w.startswith("@")), "@army")
        army_morale = self.game.emotions.get_team_average(color, "morale")
        desperation = max(0.35, (100 - army_morale) / 100)
        intensity = abs(sentiment * 12) * desperation * self.speech_decay_factor

        if target_tag in ["@army", "@all", "@troops"]:
            return self._rally_army(sentiment, intensity, color)
        return self._directed_speech(target_tag, sentiment, intensity, color)

    def _ollama_reply(self, name, square, attrs, player_text):
        sys = ("You are the inner voice of a chess piece in a morale-based war. "
               "Reply briefly (max 20 words) with emotional realism.")
        mood = f"(morale {attrs['morale']:.0f}, trust {attrs['trust']:.0f}, loyalty {attrs['loyalty']:.0f}, motivation {attrs['motivation']:.0f})"
        user = f"You are the {name} on {square.upper()} {mood}. Commander says: \"{player_text}\""
        return ollama_say(sys, user)

    def _rally_army(self, sentiment, intensity, color):
        for p in self.game.piece_profiles.values():
            if p.color == color:
                delta = sentiment * intensity * random.uniform(6, 12)
                p.morale = max(0, min(100, p.morale + delta))
                p.trust = max(0, min(100, p.trust + delta * 0.6))
                p.motivation = max(0, min(100, p.motivation + delta * 0.45))
        avg = self.game.emotions.get_team_average(color, "morale")
        attrs = {
            "morale": avg,
            "trust": self.game.emotions.get_team_average(color, "trust"),
            "loyalty": self.game.emotions.get_team_average(color, "loyalty"),
            "motivation": self.game.emotions.get_team_average(color, "motivation")
        }
        return self._ollama_reply("army", "ranks", attrs, "Your words thunder across the battlefield!")

    def _directed_speech(self, tag, sentiment, intensity, color):
        tag = tag.replace("@", "").lower()
        for sq, prof in self.game.piece_profiles.items():
            piece = self.game.board.piece_at(sq)
            if not piece or piece.color != color:
                continue
            symbol = piece.symbol().lower()
            square = chess.square_name(sq)
            combos = {square, f"{square}{symbol}", f"{symbol}{square}", symbol}
            if tag in combos:
                delta = sentiment * intensity * random.uniform(8, 15)
                prof.morale = max(0, min(100, prof.morale + delta))
                prof.trust = max(0, min(100, prof.trust + delta * 0.85))
                prof.motivation = max(0, min(100, prof.motivation + delta * 0.65))
                attrs = {"morale": prof.morale, "trust": prof.trust,
                         "loyalty": prof.loyalty, "motivation": prof.motivation}
                piece_name = {"p": "pawn", "n": "knight", "b": "bishop",
                              "r": "rook", "q": "queen", "k": "king"}[symbol]
                return self._ollama_reply(piece_name, square, attrs, "The commander calls to you!")
        return f"Your voice echoes in vain — no @{tag} listens."
