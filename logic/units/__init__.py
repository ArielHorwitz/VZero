
import pkgutil, copy
from logic.mechanics.common import *


DEFAULT_HITBOX = 20


class Unit:
    def __init__(self, api, uid, allegience, name=None, hitbox=DEFAULT_HITBOX):
        self.__uid = uid
        self._name = 'Unnamed unit' if name is None else name
        self._hitbox = hitbox
        self.allegience = allegience
        self.color_code = 1
        self.startup(api)

    @property
    def name(self):
        return f'{self._name} ({self.uid})'

    def startup(self, api):
        pass

    def poll_abilities(self, api):
        return None

    @property
    def HITBOX(self):
        return self._hitbox

    @property
    def uid(self):
        return self.__uid


class Player(Unit):
    SPRITE = 'cat.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 1000},
        STAT.HP: {VALUE.CURRENT: 100, VALUE.MAX_VALUE: 100, VALUE.DELTA: 0.02},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 1},
        STAT.MANA: {VALUE.CURRENT: 100, VALUE.MAX_VALUE: 100, VALUE.DELTA: 0.05},
        STAT.RANGE: {VALUE.CURRENT: 100},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
    }

    def startup(self, api):
        self._name = 'Player'
        self.color_code = 0


DEFAULT_STARTING_STATS = {
    STAT.POS_X: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.POS_Y: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.GOLD: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.HP: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: 0,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MOVE_SPEED: {
        VALUE.CURRENT: 1,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MANA: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_00,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.RANGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.DAMAGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.ATTACK_SPEED: {
        VALUE.CURRENT: 100,
        VALUE.MIN_VALUE: 10,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.LIFESTEAL: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
}
SPAWN_WEIGHTS = {
    'ratzan': (4, 7),
    'blood-imp': (4, 4),
    'null-ice': (3, 1),
    'fire-elemental': (2, 1),
    'winged-snake': (0, 1),
    'folphin': (3,1),
    'treasure': (0, 1),
    'heros-treasure': (0,1),
}


def get_starting_stats(custom=None, base=None):
    stats = copy.deepcopy(DEFAULT_STARTING_STATS if base is None else base)
    if custom is not None:
        for stat in STAT:
            if stat in custom:
                for value in VALUE:
                    if value in custom[stat]:
                        stats[stat][value] = custom[stat][value]
    return stats


def get_all_units():
    units = {}
    for loader, modname, ispkg in pkgutil.iter_modules(__path__, __name__+'.'):
        module = __import__(modname, fromlist='UNITS')
        for unit_name, unit_cls in module.UNITS.items():
            if unit_name in units:
                raise ValueError(f'Unit name duplicate: {unit_name} \
                                 ({units[unit_name]} and {unit_cls})')
            print(f'Found unit: {unit_name:<30} {unit_cls}')
            units[unit_name] = unit_cls
    return units
