import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data.load import resource_name


DEFAULT_HITBOX = 20


class Unit:
    def __init__(self, api, uid, name, allegiance, params=None):
        self.__uid = uid
        self.name = name
        self.allegience = allegiance
        self.color = (1, 1, 1)
        logger.debug(f'Sending params to agency subclass: {params}')
        self.setup(api, **params)

    def setup(self, api, **params):
        pass

    def poll_abilities(self, api):
        return None

    @property
    def uid(self):
        return self.__uid

    @property
    def sprite(self):
        return resource_name(self.name)

    @property
    def debug_str(self):
        return f'{self} debug str undefined.'
