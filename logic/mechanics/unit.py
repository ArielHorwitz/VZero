import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data import resource_name


class Unit:
    def __init__(self, api, uid, name, setup_params=None, allegiance=1):
        setup_params = {} if setup_params is None else setup_params
        self.api = api
        self.__uid = uid
        self.name = name
        self.allegiance = allegiance
        self.color = (1, 1, 1)
        self.abilities = []
        self._last_passive = -1
        self.__debug_str = f'{self} debug str undefined.'
        self._debug_last_action = 0
        logger.debug(f'Sending setup params to agency subclass: {setup_params}')
        self.setup(**setup_params)

    def set_abilities(self, aids):
        aids = set(aids)
        self.abilities = list(aids)

    def setup(self, **setup_params):
        pass

    def poll_abilities(self, api):
        return None

    def do_passive(self, api):
        if len(self.abilities) == 0:
            return
        dt = api.tick - self._last_passive
        self._last_passive = api.tick
        for aid in self.abilities:
            logger.debug(f'{self.uid} doing passive {aid} @ {self._last_passive}, dt: {dt}')
            api.abilities[aid].passive(api, self.uid, dt)

    def action_phase(self):
        self._debug_last_action = self.api.tick
        return self.poll_abilities(self.api)

    @property
    def uid(self):
        return self.__uid

    @property
    def sprite(self):
        return resource_name(self.name)

    @property
    def debug_str(self):
        return self.__debug_str
