import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data.load import resource_name


PASSIVE_RESOLUTION = 60


class Unit:
    def __init__(self, api, uid, name, allegiance, params=None):
        self.__uid = uid
        self.name = name
        self.allegience = allegiance
        self.color = (1, 1, 1)
        self.abilities = []
        self._last_passive = -1
        logger.debug(f'Sending params to agency subclass: {params}')
        self.setup(api, **params)

    def set_abilities(self, aids):
        aids = set(aids)
        self.abilities = list(aids)

    def setup(self, api, **params):
        pass

    def poll_abilities(self, api):
        self.do_passive(api)
        return self.do_agency(api)

    def do_agency(self, api):
        return None

    def do_passive(self, api):
        if api.tick > self._last_passive + PASSIVE_RESOLUTION:
            self._last_passive = api.tick
            for aid in self.abilities:
                api.abilities[aid].passive(api, self.uid, PASSIVE_RESOLUTION)

    @property
    def uid(self):
        return self.__uid

    @property
    def sprite(self):
        return resource_name(self.name)

    @property
    def debug_str(self):
        return f'{self} debug str undefined.'
