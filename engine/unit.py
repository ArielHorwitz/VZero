import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data.assets import Assets


class Unit:
    def __init__(self, uid, name):
        self.__uid = uid
        self.__debug_str = f'Unit #{uid} `debug_str` undefined.'

    def passive_phase(self):
        pass

    def action_phase(self):
        pass

    @property
    def uid(self):
        return self.__uid

    @property
    def sprite(self):
        return Assets.FALLBACK_SPRITE

    @property
    def debug_str(self):
        return self.__debug_str
