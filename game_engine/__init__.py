# game_engine/__init__.py
"""
The game_engine package contains all core systems for Charisma Chess:
game logic, emotion mechanics, speech system, and move handling.
"""

from .game_logic import CharismaChess
from .emotions import EmotionSystem
from .speech import SpeechSystem
from .moves import MoveEngine
from .config import MOVE_RE, HEROIC_BELIEF_THRESHOLD, PSEUDO_BELIEF_THRESHOLD
