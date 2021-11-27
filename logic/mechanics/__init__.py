import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import pkgutil, importlib
import enum
from pathlib import Path
from nutil.vars import AutoIntEnum
from data import ROOT_DIR
from data.load import RDF
from data.settings import Settings


MOD_NAME = Settings.get_setting('mod')
MODS_DIR = ROOT_DIR / 'logic' / 'mods'


__mod_name = '_fallback'  # Set to fallback before searching
logger.info(f'Looking for mod {MOD_NAME} in {MODS_DIR}')

for loader, modname, ispkg in pkgutil.iter_modules([MODS_DIR]):
    logger.debug(f'Qualifying {modname} as mod (ispkg: {ispkg})')
    if not ispkg or modname != MOD_NAME:
        logger.info(f'Disqualified {modname}')
        continue
    logger.info(f'Found mod: {modname}')
    __mod_name = modname
    break
else:
    logger.warning(f'Cannot find mod: {MOD_NAME}, fallback: {__mod_name}')


def import_mod_module(module_name, pkg=__mod_name):
    return importlib.import_module(f'.{module_name}', f'logic.mods.{pkg}')

MOD_PKG = importlib.import_module(f'.{__mod_name}', f'logic.mods')
logger.info(f'Imported mod package: {MOD_PKG}')


def ability_internal_name(name):
    return name.upper().replace(' ', '_')


# DEFINITIONS
# We must know the count and names of abilities (as loaded from config).
# This requires a particular import sequence, since mods require to know
# the abilities and stats as defined here. Hence we must do this before
# the logic.mods package is imported as it will import us for these names.
ABILITY = AutoIntEnum('ABILITY', [
    *[f'{ability_internal_name(a)}' for a in RDF.load(RDF.CONFIG_DIR / 'abilities.bal').keys()]
])

STAT = AutoIntEnum('STAT', [
    'POS_X',
    'POS_Y',
    'HITBOX',
    'HP',
    *(_.upper() for _ in MOD_PKG.STATS),
])

STATUS = AutoIntEnum('STATUS', [
    *(_.upper() for _ in MOD_PKG.STATUSES),
])


assert STAT.POS_X + 1 == STAT.POS_Y


# VALUE TYPES
class VALUE(AutoIntEnum):
    CURRENT = enum.auto()
    DELTA = enum.auto()
    TARGET_VALUE = enum.auto()
    MIN_VALUE = enum.auto()
    MAX_VALUE = enum.auto()


class STATUS_VALUE(AutoIntEnum):
    DURATION = enum.auto()
    STACKS = enum.auto()


class FAIL_RESULT(enum.Enum):
    CRITICAL_ERROR = enum.auto()
    INACTIVE = enum.auto()
    OUT_OF_BOUNDS = enum.auto()
    MISSING_COST = enum.auto()
    OUT_OF_RANGE = enum.auto()
    ON_COOLDOWN = enum.auto()
    MISSING_TARGET = enum.auto()


class COLOR:
    BLACK = (0, 0, 0)
    WHITE = (1, 1, 1)
    RED = (1, 0, 0)
    GREEN = (0, 1, 0)
    BLUE = (0, 0, 1)
    YELLOW = (1, 1, 0)
    PURPLE = (1, 0, 1)
    CYAN = (0, 1, 1)


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


for enumerator in (STAT, VALUE, STATUS, STATUS_VALUE, ABILITY):
    __DEBUG = f'Using {enumerator.__name__} indices:'
    for stat in enumerator:
        __DEBUG += f'{stat.value} {stat.name}; '
    logger.info(__DEBUG)
