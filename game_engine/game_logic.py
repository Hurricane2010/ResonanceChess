import chess, requests
from piece_profile import PieceProfile
from game_engine.config import HEROIC_BELIEF_THRESHOLD, PSEUDO_BELIEF_THRESHOLD
from game_engine.emotions import EmotionSystem
from game_engine.speech import SpeechSystem
from game_engine.moves import MoveEngine

class CharismaChess:
    """Main controller tying together all subsystems."""

    def __init__(self):
        # Core board setup
        self.board = chess.Board()

        # Initialize emotional profiles for each piece
        self.piece_profiles = {
            sq: PieceProfile(sq, p.color)
            for sq in chess.SQUARES
            if (p := self.board.piece_at(sq))
        }

        # Core subsystems
        self.emotions = EmotionSystem(self.piece_profiles)
        self.speech = SpeechSystem(self)
        self.moves = MoveEngine(self)

    # ---------------- Proxy Methods (to preserve backward compatibility) ----------------
    def get_team_average(self, color, attr):
        """Backward-compatible shortcut for EmotionSystem.get_team_average"""
        return self.emotions.get_team_average(color, attr)

    def adjust_emotions(self, move_score, color):
        """Backward-compatible shortcut for EmotionSystem.adjust_emotions"""
        return self.emotions.adjust_emotions(move_score, color)

    def team_belief(self, color):
        """Shortcut to compute team trust/morale mix."""
        return self.emotions.team_belief(color)

    # ---------------- Main Game Flow ----------------
    def make_move(self, text):
        """
        Handles player commands and passes them through the MoveEngine.
        Also integrates morale/emotion updates and speech responses.
        """
        return self.moves.make_move(text)

    def enemy_move(self, force_black=False):
        """
        Handles Stockfish/Lichess AI replies for black.
        Falls back to random legal moves if API call fails.
        """
        return self.moves.enemy_move(force_black)
    
        # ---------------- Move profile remapping ----------------
    def apply_move_profiles(self, move, mover_color):
        """Remap emotion profiles to new squares without resetting them."""
        from_sq, to_sq = move.from_square, move.to_square
        # capture
        if self.board.piece_at(to_sq) and self.board.piece_at(to_sq).color != mover_color:
            self.piece_profiles.pop(to_sq, None)
        # en passant
        if self.board.is_en_passant(move):
            ep_sq = move.to_square - 8 if mover_color == chess.WHITE else move.to_square + 8
            self.piece_profiles.pop(ep_sq, None)
        # move piece profile
        mover_prof = self.piece_profiles.pop(from_sq, None)
        if mover_prof:
            mover_prof.square = to_sq
            self.piece_profiles[to_sq] = mover_prof
        # handle castling rook remap
        castles = {
            (chess.E1, chess.G1): (chess.H1, chess.F1),
            (chess.E1, chess.C1): (chess.A1, chess.D1),
            (chess.E8, chess.G8): (chess.H8, chess.F8),
            (chess.E8, chess.C8): (chess.A8, chess.D8),
        }
        r_from, r_to = castles.get((move.from_square, move.to_square), (None, None))
        if r_from is not None and r_to is not None:
            rook_prof = self.piece_profiles.pop(r_from, None)
            if rook_prof:
                rook_prof.square = r_to
                self.piece_profiles[r_to] = rook_prof
