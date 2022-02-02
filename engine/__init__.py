# Engine
"""
This package provides the base classes for
the logic API and other useful utilities.

Here we prepare the game logic API for the GUI.
Firstly we must allow the game logic to define
parts of the common enumerators. Since it relies
on these in runtime, we must perform this before
actually retrieving the logic API.
"""


import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import enum
from nutil.vars import AutoIntEnum
from data.assets import Assets
from data.settings import Settings
import logic


def internal_name(name):
    return name.upper().replace(' ', '_')


# Load definitions and api from logic
get_api = logic.get_api


ABILITY = AutoIntEnum('ABILITY', [internal_name(_) for _ in logic.ABILITIES])


STAT = AutoIntEnum('STAT', [
    'POS_X',
    'POS_Y',
    'WEIGHT',
    'HITBOX',
    'HP',
    *(internal_name(_) for _ in logic.STATS),
])


STATUS = AutoIntEnum('STATUS', [internal_name(_) for _ in logic.STATUSES])


assert STAT.POS_X + 1 == STAT.POS_Y


VALUE = AutoIntEnum('VALUE', ['CURRENT', 'MIN', 'MAX', 'DELTA', 'TARGET'])


STATUS_VALUE = AutoIntEnum('STATUS_VALUE', ['DURATION', 'STACKS'])


class FAIL_RESULT(enum.Enum):
    CRITICAL_ERROR = enum.auto()
    INACTIVE = enum.auto()
    MISSING_ACTIVE = enum.auto()
    MISSING_TARGET = enum.auto()
    MISSING_COST = enum.auto()
    OUT_OF_BOUNDS = enum.auto()
    OUT_OF_RANGE = enum.auto()
    OUT_OF_ORDER = enum.auto()
    ON_COOLDOWN = enum.auto()


class COLOR:
    BLACK = (0, 0, 0)
    WHITE = (1, 1, 1)
    GREY = (0.5, 0.5, 0.5)
    RED = (1, 0, 0)
    GREEN = (0, 1, 0)
    BLUE = (0, 0, 1)
    YELLOW = (1, 1, 0)
    PURPLE = (1, 0, 1)
    PINK = (0.5, 0, 0)
    CYAN = (0, 1, 1)
    BROWN = (0.5, 0.5, 0)
    LIME = (0.65, 1, 0)


# VFX
VFX = AutoIntEnum('VFX', [
    'BACKGROUND',
    'LINE',
    'CIRCLE',
    'QUAD',
    'SPRITE',
    'SFX',
])


class VisualEffect:
    VFX = VFX
    def __init__(self, eid, ticks, params=None):
        self.eid = eid
        self.total_ticks = ticks
        self.elapsed_ticks = 0
        self.params = {} if params is None else params

        if eid is self.VFX.SFX:
            category = 'ability'
            if 'category' in params:
                category = params['category']
            volume = 'sfx'
            if 'volume' in params:
                volume = params['volume']
            Assets.play_sfx(
                category, params['sfx'],
                volume=Settings.get_volume(volume),
                allow_exception=False)
            self.total_ticks = 0

    def tick(self, ticks):
        self.elapsed_ticks += ticks

    @property
    def active(self):
        return self.elapsed_ticks <= self.total_ticks

    def __repr__(self):
        return f'<VisualEffect eid={self.eid.name} elapsed={self.elapsed_ticks} total={self.total_ticks}>'


for enumerator in (STAT, VALUE, STATUS, STATUS_VALUE, ABILITY):
    __DEBUG = f'Using {enumerator.__name__} indices:'
    for stat in enumerator:
        __DEBUG += f'{stat.value} {stat.name}; '
    logger.info(__DEBUG)
