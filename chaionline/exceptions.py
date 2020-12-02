class ResponseError(Exception):
    pass


class LoadConfigError(Exception):
    pass


class GameStartTimeout(Exception):
    pass


class GameSearchTimeout(Exception):
    pass


class StreamItemError(Exception):
    pass


class GameError(Exception):
    pass


class GameSearchMaxTries(Exception):
    pass


class GameDataParseError(Exception):
    pass
