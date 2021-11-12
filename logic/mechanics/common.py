import enum
from nutil.display import adis
from nutil.vars import AutoIntEnum
from data.load import load_abilities as __mechanics_common_load_abilities_


ABILITY = ABILITIES = AutoIntEnum('ABILITIES', [
    *[f'{internal_name.upper()}' for internal_name in \
      __mechanics_common_load_abilities_().keys()]
])


class COLOR:
    BLACK = (0, 0, 0)
    WHITE = (1, 1, 1)
    RED = (1, 0, 0)
    GREEN = (0, 1, 0)
    BLUE = (0, 0, 1)
    YELLOW = (1, 1, 0)
    PURPLE = (1, 0, 1)
    CYAN = (0, 1, 1)


class FAIL_RESULT(enum.Enum):
    CRITICAL_ERROR = enum.auto()
    INACTIVE = enum.auto()
    OUT_OF_BOUNDS = enum.auto()
    MISSING_COST = enum.auto()
    OUT_OF_RANGE = enum.auto()
    ON_COOLDOWN = enum.auto()
    MISSING_TARGET = enum.auto()


# BASE STATS
class STAT(AutoIntEnum):
    # Builtins - do not touch
    POS_X = enum.auto()
    POS_Y = enum.auto()
    HP = enum.auto()
    MANA = enum.auto()
    HITBOX = enum.auto()

    # Stats required by mechanics
    MOVE_SPEED = enum.auto()
    GOLD = enum.auto()
    RANGE = enum.auto()
    DAMAGE = enum.auto()
    ATTACK_SPEED = enum.auto()
    LIFESTEAL = enum.auto()


assert STAT.POS_X + 1 == STAT.POS_Y


class STATUS(AutoIntEnum):
    SLOW = enum.auto()
    LIFESTEAL = enum.auto()
    SHIELD_CHANCE = enum.auto()
    SHIELD_BLOCK = enum.auto()
    WRATH = enum.auto()


# STATUSES
class STATUS_VALUE(AutoIntEnum):
    DURATION = enum.auto()
    AMPLITUDE = enum.auto()
    ENDED_NOW = enum.auto()


class VALUE(AutoIntEnum):
    CURRENT = enum.auto()
    DELTA = enum.auto()
    TARGET_VALUE = enum.auto()
    TARGET_TICK = enum.auto()
    MIN_VALUE = enum.auto()
    MAX_VALUE = enum.auto()


# VFX
class _VFX(AutoIntEnum):
    BACKGROUND = enum.auto()
    LINE = enum.auto()
    CIRCLE = enum.auto()
    SPRITE = enum.auto()
    SFX = enum.auto()


class VisualEffect:
    BACKGROUND = _VFX.BACKGROUND
    LINE = _VFX.LINE
    CIRCLE = _VFX.CIRCLE
    SPRITE = _VFX.SPRITE
    SFX = _VFX.SFX

    def __init__(self, eid, ticks, params=None):
        self.eid = eid
        self.total_ticks = ticks
        self.elapsed_ticks = 0
        self.params = {} if params is None else params

    def tick(self, ticks):
        self.elapsed_ticks += ticks

    @property
    def active(self):
        return self.elapsed_ticks <= self.total_ticks

    def __repr__(self):
        return f'<VisualEffect eid={self.eid.name} elapsed={self.elapsed_ticks} total={self.total_ticks}>'
