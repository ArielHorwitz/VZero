from logic.mechanics import import_mod_module
from logic.mechanics.common import *
abilities = import_mod_module('abilities._release')
units = import_mod_module('units')


ABILITY_CLASSES = abilities.ABILITY_CLASSES


UNIT_CLASSES = {
    'camper': units.Camper,
    'roamer': units.Roamer,
    'treasure': units.Treasure,
    'dps_meter': units.DPSMeter,
}

DEFAULT_STARTING_STATS = {
    # BUILTIN STATS
    STAT.POS_X: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.POS_Y: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.HITBOX: {
        VALUE.CURRENT: 20,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.HP: {
        VALUE.CURRENT: 1_000_000,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: 0,
    },
    # CUSTOM STATS
    STAT.MANA: {
        VALUE.CURRENT: 1_000_000,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.GOLD: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.PHYSICAL: {
        VALUE.CURRENT: 10,
        VALUE.MIN_VALUE: 2,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.FIRE: {
        VALUE.CURRENT: 10,
        VALUE.MIN_VALUE: 2,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.EARTH: {
        VALUE.CURRENT: 10,
        VALUE.MIN_VALUE: 2,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.AIR: {
        VALUE.CURRENT: 10,
        VALUE.MIN_VALUE: 2,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
    STAT.WATER: {
        VALUE.CURRENT: 10,
        VALUE.MIN_VALUE: 2,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
    },
}
