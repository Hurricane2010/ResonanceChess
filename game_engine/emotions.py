class EmotionSystem:
    """Handles morale and trust mechanics for all pieces."""

    def __init__(self, piece_profiles):
        self.piece_profiles = piece_profiles

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

    def team_belief(self, color):
        """Weighted belief metric combining trust + morale."""
        return 0.6 * self.get_team_average(color, "trust") + 0.4 * self.get_team_average(color, "morale")
