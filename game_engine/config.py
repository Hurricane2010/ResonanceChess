import re

# Move regex (supports UCI + prefixed)
MOVE_RE = re.compile(r"^[NBRQK]?[a-h][1-8][a-h][1-8][qrbn]?$", re.IGNORECASE)

# Thresholds for supernatural behavior
HEROIC_BELIEF_THRESHOLD = 95.0   # Fully illegal "reality-bending" moves
PSEUDO_BELIEF_THRESHOLD = 85.0   # Pseudo-legal (e.g., moving into check)
HEROIC_OVERRIDE_MORALE = 30      # Minimum army morale before collapse
