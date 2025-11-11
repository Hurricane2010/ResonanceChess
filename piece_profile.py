import random

class PieceProfile:
    """Represents emotional stats for a single chess piece."""

    def __init__(self, square, color):
        self.square = square
        self.color = color
        self.loyalty = random.randint(60, 80)
        self.motivation = random.randint(60, 80)
        self.morale = random.randint(60, 80)
        self.trust = random.randint(50, 70)
        self.empathy = random.randint(40, 60)

    def average(self):
        return (self.loyalty + self.motivation + self.morale +
                self.trust + self.empathy) / 5
