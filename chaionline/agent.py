from abc import abstractmethod
import chess
import random

from .enumerations import GameResult


class Agent:

    def __init__(self):
        pass

    @abstractmethod
    def step(self, board: chess.Board) -> str:
        pass

    @abstractmethod
    def result_was(self, result: GameResult):
        pass

    def reward(self):
        pass


class RandomAgent(Agent):

    def __init__(self):
        super().__init__()

    def step(self, board: chess.Board) -> str:
        moves = list(board.legal_moves)
        return str(moves[random.randint(0, len(moves) - 1)])

    def result_was(self, result: GameResult):
        if result == GameResult.DRAW:
            print('Result was a Draw')
        elif result == GameResult.WIN:
            print('Result was a Win')
        elif result == GameResult.LOSS:
            print('Result was a Loss')
