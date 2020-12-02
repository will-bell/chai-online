from typing import Dict, List, Iterable, Tuple
from time import time
from urllib import parse
import json
import threading

import requests
import yaml

from .exceptions import *
from .enumerations import Color


# TODO: Make this a singleton class
class AuthenticatedSession(requests.Session):

    def __init__(self, token: str):
        super().__init__()
        self.headers = {'Authorization': f'Bearer {token}'}


class ClientConfig:

    token: str

    def __init__(self, config_dict: Dict[str, str]):
        self.token = config_dict['token']


def load_config() -> ClientConfig:
    """Loads the client config from the client-config.yaml file

    Returns:
        ClientConfig object
    """
    with open('client-config.yaml', 'r') as config:
        try:
            client_config = ClientConfig(yaml.safe_load(config))
        except yaml.YAMLError:
            raise LoadConfigError
    return client_config


def response_to_json(response: requests.Response):
    return response.json()


class Client:

    session: requests.Session

    base_url: str

    def __init__(self):
        self.client_config = load_config()
        self.session = AuthenticatedSession(self.client_config.token)
        self.base_url = 'https://lichess.org/'

        self._account_info = None

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = parse.urljoin(self.base_url, path)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as e:
            # TODO: add logging for this exception
            raise e
        if not response.ok:
            # TODO: add logging for this exception
            raise ResponseError
        return response

    def get(self, path: str, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request('POST', path, **kwargs)

    def _get_account_info(self):
        return response_to_json(self.get('api/account'))

    @property
    def account_info(self) -> dict:
        if self._account_info is None:
            self._account_info = self._get_account_info()
        return self._account_info

    @property
    def account_name(self):
        return self.account_info['username']

    @property
    def account_id(self):
        return self.account_info['id']


def white_moved(moves: List[str]):
    if len(moves) % 2:
        return moves[-1]


def black_moved(moves: List[str]):
    if not len(moves) % 2:
        return moves[-1]


class GameData:

    id: str

    my_color: Color

    opponent_color: Color

    def __init__(self, game_id: str, my_color: Color, opponent_color: Color):
        self.id = game_id
        self.my_color = my_color
        self.opponent_color = opponent_color


def threaded(func):

    def threaded_func(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return thread.join()

    return threaded_func


class GameClient(Client):

    _game_event_streams: Dict[str, Iterable]

    def __init__(self):
        super().__init__()
        self._game_event_streams = {}
        self._game_accept_timeout = 2.
        self._game_search_timeout = 30.
        self._game_abort_time = 300
        self._n_search_attempts = 1
        self._ai_level = 2

    def _wait_for_game_start(self) -> str:
        """

        Returns:
            Game ID for the new game

        Raises:
            GameStartTimeout: If the search time exceeds the client's `game_accept_timeout` parameter
        """
        start_time = time()
        stream = self.get('api/stream/event', stream=True)
        lines = stream.iter_lines()
        while (time() - start_time) < self._game_accept_timeout:
            update = json.loads(next(lines).decode('utf-8'))
            if update:
                if update['type'] == 'gameStart':
                    return update['game']['id']
        raise GameStartTimeout

    def _accept_challenge(self, challenge_id: str) -> str:
        """

        Args:
            challenge_id (str): ID for the challenge

        Returns:
            ID for the new game
        """
        self.post(f'api/challenge/{challenge_id}/accept')
        game_id = self._wait_for_game_start()
        return game_id

    def _search_for_game(self, search_timeout: float) -> str:
        """

        Args:
            search_timeout (float): Max allotted time for the search

        Returns:
            ID for the new game

        Raises:
            GameStartTimeout: If the search time exceeds the client's `game_search_timeout` parameter
        """
        start_time = time()
        stream = self.get('api/stream/event', stream=True)
        lines = stream.iter_lines()
        while (time() - start_time) < search_timeout:
            update = json.loads(next(lines).decode('utf-8'))
            if update:
                if update['type'] == 'challenge':
                    challenge_id = update['id']
                    try:
                        return self._accept_challenge(challenge_id)
                    except GameStartTimeout:
                        # TODO: add logging for this exception
                        pass
        raise GameSearchTimeout

    def _get_game_event_stream(self, game_id: str):
        try:
            return self._game_event_streams[game_id]
        except KeyError:
            stream = self.get(f'api/bot/game/stream/{game_id}', stream=True)
            return stream.iter_lines()

    def _get_full_game_state(self, game_id: str):
        lines = self._get_game_event_stream(game_id)
        update = next(lines).decode('utf-8')

        # Full game state should be the first item in the stream
        if update:
            item = json.loads(update)
            if item['type'] == 'gameFull':
                return item
        raise GameDataParseError

    def _determine_colors(self, full_game_state: dict) -> Tuple[Color, Color]:
        """

        Args:
            full_game_state:

        Returns:
            (my color, opponent color)
        """
        # If both white and black have IDs, then determine colors by matching up the account ID
        if ('id' in full_game_state['white'].keys()) and ('id' in full_game_state['black'].keys()):
            if full_game_state['white']['id'] == self.account_id:
                return Color.WHITE, Color.BLACK
            elif full_game_state['black']['id'] == self.account_id:
                return Color.BLACK, Color.WHITE

        # Otherwise, determine colors by which is the Lichess AI
        else:
            if 'aiLevel' in full_game_state['black'].keys():
                return Color.WHITE, Color.BLACK
            elif 'aiLevel' in full_game_state['white'].keys():
                return Color.BLACK, Color.WHITE

        raise GameDataParseError

    def _parse_game_data(self, game_id: str) -> GameData:
        """

        Args:
            game_id:

        Returns:

        """
        full_game_state = self._get_full_game_state(game_id)
        my_color, opponent_color = self._determine_colors(full_game_state)
        return GameData(game_id, my_color, opponent_color)

    def find_opponent(self, search_timeout: float = None, n_search_attempts: int = None) -> GameData:
        """

        Args:
            search_timeout:
            n_search_attempts:

        Returns:

        """
        search_timeout = self._game_search_timeout if search_timeout is None else search_timeout
        n_search_attempts = self._n_search_attempts if n_search_attempts is None else n_search_attempts
        search_count = 0
        while 1:
            try:
                new_game_id = self._search_for_game(search_timeout)
                break
            except GameStartTimeout:
                search_count += 1

            if search_count >= n_search_attempts:
                # TODO: add logging for this exception
                raise GameSearchMaxTries

        self._game_event_streams[new_game_id] = self._get_game_event_stream(new_game_id)
        game_data = self._parse_game_data(new_game_id)
        return game_data

    def challenge_ai(self, ai_level: int = None):
        """

        Args:
            ai_level:

        Returns:

        """
        ai_level = self._ai_level if ai_level is None else ai_level
        params = {
            'level': ai_level,
            'clock.limit': None,
            'clock.increment': None,
            'days': None,
            'color': 'white',
            'variant': None,
            'fen': None,
        }
        self.post('api/challenge/ai', json=params)
        new_game_id = self._wait_for_game_start()

        self._game_event_streams[new_game_id] = self._get_game_event_stream(new_game_id)
        game_data = self._parse_game_data(new_game_id)
        return game_data

    def wait_for_opponent_move(self, game_data: GameData) -> str:
        game_id, opponent_color = game_data.id, game_data.opponent_color
        time_start = time()
        lines = self._get_game_event_stream(game_id)
        while (time() - time_start) < self._game_abort_time:
            update = next(lines).decode('utf-8')
            if update:
                item = json.loads(update)
                if item['type'] == 'gameState':
                    moves = item['moves'].split(' ')
                    if opponent_color == Color.WHITE and white_moved(moves):
                        return moves[-1]
                    elif opponent_color == Color.BLACK and black_moved(moves):
                        return moves[-1]

        raise GameError

    def _game_over(self, game_id: str):
        self._game_event_streams.pop(game_id)

    def resign(self, game_data: GameData):
        if game_data.id in self._game_event_streams:
            self.post(f'api/bot/game/{game_data.id}/resign')
            self._game_over(game_data.id)

    def make_move(self, game_data: GameData, move: str):
        """Makes a move to the current game

        This should be the last call before the end of a training loop.

        Args:
            game_data:
            move: desired move described in PGN format
        """
        self.post(f'api/bot/game/{game_data.id}/move/{move}')
