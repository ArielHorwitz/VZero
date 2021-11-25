import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from enum import IntEnum
from nutil.vars import AutoIntEnum, normalize, nsign_str
from logic.mechanics.common import *


def str2item(name):
    return getattr(ITEM, name.upper().replace(' ', '_'))


ITEM = AutoIntEnum('ITEM', [
    'BRANCH',
    'PHYSICAL_LEAF',
    'FIRE_LEAF',
    'EARTH_LEAF',
    'AIR_LEAF',
    'WATER_LEAF',
    'HEART',
    'VIAL'
])
ICAT = ITEM_CATEGORIES = IntEnum('ITEM_CATEGORIES', [
    'BASIC',
    'HERBAL',
    'POTION',
])

class ItemData:
    def __init__(self, category, cost, stats=None):
        self.category = category
        self.cost = cost
        self.stats = stats if stats is not None else {}

ITEM_STATS = {
    ITEM.BRANCH: ItemData(category=ICAT.BASIC, cost=25, stats={
            STAT.HP: {VALUE.DELTA: 0.0005, VALUE.MAX_VALUE: 1},
            STAT.MANA: {VALUE.DELTA: 0.0005, VALUE.MAX_VALUE: 1},
            STAT.PHYSICAL: {VALUE.CURRENT: 1},
            STAT.FIRE: {VALUE.CURRENT: 1},
            STAT.EARTH: {VALUE.CURRENT: 1},
            STAT.AIR: {VALUE.CURRENT: 1},
            STAT.WATER: {VALUE.CURRENT: 1},
        }),
    ITEM.PHYSICAL_LEAF: ItemData(category=ICAT.HERBAL, cost=125, stats={STAT.PHYSICAL: {VALUE.CURRENT: 5}}),
    ITEM.FIRE_LEAF: ItemData(category=ICAT.HERBAL, cost=125, stats={STAT.FIRE: {VALUE.CURRENT: 5}}),
    ITEM.EARTH_LEAF: ItemData(category=ICAT.HERBAL, cost=125, stats={STAT.EARTH: {VALUE.CURRENT: 5}}),
    ITEM.AIR_LEAF: ItemData(category=ICAT.HERBAL, cost=125, stats={STAT.AIR: {VALUE.CURRENT: 5}}),
    ITEM.WATER_LEAF: ItemData(category=ICAT.HERBAL, cost=125, stats={STAT.WATER: {VALUE.CURRENT: 5}}),
    ITEM.HEART: ItemData(category=ICAT.POTION, cost=225, stats={STAT.HP: {VALUE.DELTA: 0.0030, VALUE.MAX_VALUE: 6}}),
    ITEM.VIAL: ItemData(category=ICAT.POTION, cost=75, stats={STAT.MANA: {VALUE.DELTA: 0.0015, VALUE.MAX_VALUE: 3}}),
}


def item_repr(item):
    name = item.name.lower().capitalize().replace('_', ' ')
    cost = ITEM_STATS[item].cost
    s = []
    for stat, values in ITEM_STATS[item].stats.items():
        v = []
        for value_name, value in values.items():
            value_name = '' if value_name is VALUE.CURRENT else f' {value_name.name.lower()}'
            value = f'{nsign_str(value)}'
            v.append(f'{value}{value_name}')
        stat_name = stat.name.lower().capitalize().replace('_', ' ')
        s.append(f'> {stat_name}: {", ".join(v)}')
    nl = "\n"
    category = ITEM_STATS[item].category.name.lower().capitalize()
    r = f'{name}: {cost} gold\n{category}\n\n{nl.join(s)}'
    return r


logger.info('Initializing shop values:')
for item in ITEM:
    logger.info(f'{item.value:>2} - {item.name}')


class Shop:
    @classmethod
    def buy_item(cls, api, uid, item):
        item = cls.find_iid(item)
        assert item is not None

        icat = round(api.get_status(uid, STATUS.SHOP))
        if icat != ITEM_STATS[item].category.value:
            logger.debug(f'{api.units[uid].name} missing shop status for category: {icat} (asking for category {ITEM_STATS[item].category.name} {ITEM_STATS[item].category.value})')
            return FAIL_RESULT.MISSING_TARGET

        if not cls.check_cost(api, uid, item):
            logger.debug(f'{api.units[uid].name} missing gold for: {item.name} ({item.value})')
            return FAIL_RESULT.MISSING_COST

        result = cls._do_buy(api, uid, item)

        # api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'shop'})
        logger.debug(f'{api.units[uid].name} bought item: {item.name} ({item.value})')
        return result

    @classmethod
    def find_iid(cls, iid):
        for item in ITEM:
            if item.value == round(iid):
                return item
        return None

    @classmethod
    def check_cost(cls, api, uid, item):
        return api.get_stats(uid, STAT.GOLD) >= ITEM_STATS[item].cost

    @classmethod
    def _do_buy(cls, api, uid, item):
        cls.apply_cost(api, uid, item)
        cls.apply_stats(api, uid, item)

    @classmethod
    def apply_cost(cls, api, uid, item):
        api.set_stats(uid, STAT.GOLD, -ITEM_STATS[item].cost, additive=True)

    @classmethod
    def apply_stats(cls, api, uid, item):
        for stat, values in ITEM_STATS[item].stats.items():
            for value_name, value in values.items():
                api.set_stats(uid, stat, value, value_name=value_name, additive=True)
