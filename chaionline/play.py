from abc import abstractmethod
from os import system, name, remove
import threading

import cairosvg
import matplotlib.pyplot as plt
import matplotlib.image as img

import chess
import chess.svg

from .agent import Agent
from .client import Client, GameClient, GameData
from .enumerations import Color, GameResult


def clear():
    # for windows
    if name == 'nt':
        _ = system('cls')

    # for mac and linux(here, os.name is 'posix')
    else:
        _ = system('clear')


def print_board(board):
    clear()
    print(board)


class Play:

    def __init__(self, client: Client):
        self._client = client

    @abstractmethod
    def _loop(self):
        """Main game loop for the play
        """
        pass


class PlayOnline(Play):

    _client: GameClient

    _player: Agent

    def __init__(self, client: GameClient, player: Agent, show_ascii_board: bool = False):
        self._player = player
        self._show_ascii_board = show_ascii_board
        super().__init__(client)

    @abstractmethod
    def find_game(self) -> GameData:
        pass

    def _loop(self):
        """Game loop for online play

        Loop goes as...

        Find a game
        While the game is not done:
            If it is our turn:
                Observe the board
                Pick a move
                Make the move
        Game is over. Check if we won, lost, a draw occurred, or the other player resigned.
        Tell the agent the result
        Return
        """
        game_data = self.find_game()

        # Need to make a local board for our own processing
        board = chess.Board()

        # If my color is white, then I'm making the first move
        if game_data.my_color == Color.WHITE:
            move = self._player.step(board)
            board.push(chess.Move.from_uci(move))
            self._client.make_move(game_data, move)

        # Until the game is over
        while 1:
            # Wait for the opponent to move, then push its move to the local board
            opponent_move = self._client.wait_for_opponent_move(game_data)
            board.push(chess.Move.from_uci(opponent_move))

            # Print out the current state of the board if desired
            if self._show_ascii_board:
                print_board(board)
                try:
                    remove("tmp/output.png")
                except OSError:
                    pass
                png_file = open("tmp/output.png", "w")
                cairosvg.svg2png(str(chess.svg.board(board=board)), write_to='tmp/output.png')
                png_file.close()
                im = img.imread('tmp/output.png')
                plt.imshow(im)
                plt.show()

            # Is there an end condition?
            if board.is_game_over():
                break

            # Invoke the player to select a move. Then push it to the local and remote boards.
            move = self._player.step(board)
            board.push(chess.Move.from_uci(move))
            self._client.make_move(game_data, move)

            # Print out the current state of the board if desired
            if self._show_ascii_board:
                print_board(board)
                try:
                    remove("tmp/output.png")
                except OSError:
                    pass
                png_file = open("tmp/output.png", "w")
                cairosvg.svg2png(str(chess.svg.board(board=board)), write_to='tmp/output.png')
                png_file.close()
                im = img.imread('tmp/output.png')
                plt.imshow(im)
                plt.draw()

            # Is there an end condition
            if board.is_game_over():
                break

        # Determine the result of the game
        if board.result() == "1/2-1/2":
            result = GameResult.DRAW
        elif game_data.my_color == Color.WHITE:
            result = GameResult.WIN if board.result() == "1-0" else GameResult.LOSS
        else:
            result = GameResult.WIN if board.result() == "0-1" else GameResult.LOSS

        # Tell the agent the result
        self._player.result_was(result)

        return

    # def play


class PlayAgainstHuman(PlayOnline):

    def __init__(self, client: GameClient, player: Agent, show_ascii_board: bool = False):
        super().__init__(client, player, show_ascii_board)

    def find_game(self) -> GameData:
        return self._client.find_opponent()


class PlayAgainstAI(PlayOnline):

    _ai_level: int

    def __init__(self, client: GameClient, player: Agent, ai_level: int = 1, show_ascii_board: bool = False):
        self._ai_level = min(8, max(1, ai_level))
        super().__init__(client, player, show_ascii_board)

    def find_game(self) -> GameData:
        return self._client.challenge_ai(self._ai_level)
