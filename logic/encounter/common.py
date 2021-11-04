import enum
from nutil.vars import AutoIntEnum
from logic.encounter.stats import STAT, VALUE, STATUS, STATUS_VALUE, argmin


class _VFX(AutoIntEnum):
    BACKGROUND = enum.auto()
    LINE = enum.auto()
    SFX = enum.auto()


class VisualEffect:
    BACKGROUND = _VFX.BACKGROUND
    LINE = _VFX.LINE
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


class ABILITIES(AutoIntEnum):
    # Basic
    MOVE = enum.auto()
    STOP = enum.auto()
    LOOT = enum.auto()
    # Spells
    ATTACK = enum.auto()
    BLOODLUST = enum.auto()
    BEAM = enum.auto()
    BLINK = enum.auto()
    # Items
    VIAL = enum.auto()
    SHARD = enum.auto()
    MOONSTONE = enum.auto()
    BRANCH = enum.auto()


class RESULT(enum.Enum):
    NOMINAL = enum.auto()
    MISSING_RESULT = enum.auto()
    INACTIVE = enum.auto()
    OUT_OF_BOUNDS = enum.auto()
    MISSING_COST = enum.auto()
    OUT_OF_RANGE = enum.auto()
    ON_COOLDOWN = enum.auto()
    MISSING_TARGET = enum.auto()
