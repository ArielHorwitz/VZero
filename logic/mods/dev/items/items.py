import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import enum
from nutil.vars import normalize, nsign_str
from logic.mechanics.common import *


def str2item(name):
    return getattr(ITEM, name.upper().replace(' ', '_'))


class ITEM(enum.IntEnum):
    BRANCH = enum.auto()
    PHYSICAL_LEAF = enum.auto()
    FIRE_LEAF = enum.auto()
    EARTH_LEAF = enum.auto()
    AIR_LEAF = enum.auto()
    WATER_LEAF = enum.auto()
    HEART = enum.auto()
    VIAL = enum.auto()


ITEM_STATS = {
    ITEM.BRANCH: {
        'cost': 25,
        'stats': {
            STAT.HP: {VALUE.DELTA: 0.0005, VALUE.MAX_VALUE: 1},
            STAT.MANA: {VALUE.DELTA: 0.0005, VALUE.MAX_VALUE: 1},
            STAT.PHYSICAL: {VALUE.CURRENT: 1},
            STAT.FIRE: {VALUE.CURRENT: 1},
            STAT.EARTH: {VALUE.CURRENT: 1},
            STAT.AIR: {VALUE.CURRENT: 1},
            STAT.WATER: {VALUE.CURRENT: 1},
        },
    },
    ITEM.PHYSICAL_LEAF: {'cost': 125, 'stats': {STAT.PHYSICAL: {VALUE.CURRENT: 5}}},
    ITEM.FIRE_LEAF: {'cost': 125, 'stats': {STAT.FIRE: {VALUE.CURRENT: 5}}},
    ITEM.EARTH_LEAF: {'cost': 125, 'stats': {STAT.EARTH: {VALUE.CURRENT: 5}}},
    ITEM.AIR_LEAF: {'cost': 125, 'stats': {STAT.AIR: {VALUE.CURRENT: 5}}},
    ITEM.WATER_LEAF: {'cost': 125, 'stats': {STAT.WATER: {VALUE.CURRENT: 5}}},
    ITEM.HEART: {'cost': 225, 'stats': {STAT.HP: {VALUE.DELTA: 0.0030, VALUE.MAX_VALUE: 6}}},
    ITEM.VIAL: {'cost': 75, 'stats': {STAT.MANA: {VALUE.DELTA: 0.0015, VALUE.MAX_VALUE: 3}}},
}


def item_repr(item):
    name = item.name.lower().capitalize().replace('_', ' ')
    cost = ITEM_STATS[item]['cost']
    s = []
    for stat, values in ITEM_STATS[item]['stats'].items():
        v = []
        for value_name, value in values.items():
            value_name = '' if value_name is VALUE.CURRENT else f' {value_name.name.lower()}'
            value = f'{nsign_str(value)}'
            v.append(f'{value}{value_name}')
        stat_name = stat.name.lower().capitalize().replace('_', ' ')
        s.append(f'> {stat_name}: {", ".join(v)}')
    nl = "\n"
    r = f'{name}: {cost} gold\n{nl.join(s)}'
    return r


logger.info('Initializing shop values:')
for item in ITEM:
    logger.info(f'{item.value:>2} - {item.name}')
