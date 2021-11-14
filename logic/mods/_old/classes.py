from logic.mechanics import import_mod_module
from logic.mechanics.common import *
abilities = import_mod_module('abilities')
units = import_mod_module('units')


ABILITY_CLASSES = {
    'move': abilities.Move,
    'loot': abilities.Loot,
    'attack': abilities.Attack,
    'teleport': abilities.Teleport,
    'slow': abilities.Slow,
    'lifesteal': abilities.Lifesteal,
    'shield': abilities.Shield,
    'blast': abilities.Blast,
}

UNIT_CLASSES = {
    'camper': units.Camper,
    'roamer': units.Roamer,
    'treasure': units.Treasure,
    'dps_meter': units.DPSMeter,
}


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
    STAT.HITBOX: {
        VALUE.CURRENT: 20,
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
    STAT.MANA: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_00,
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
    STAT.MOVE_SPEED: {
        VALUE.CURRENT: 1,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
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
