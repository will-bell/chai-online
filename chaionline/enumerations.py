from enum import Enum


class Pieces(Enum):
    KING = 1
    QUEEN = 2
    ROOK = 3
    BISHOP = 4
    KNIGHT = 5
    PAWN = 6


class Color(Enum):
    WHITE = 1
    BLACK = 2


class GameResult(Enum):
    WIN = 1
    LOSS = 2
    DRAW = 3
