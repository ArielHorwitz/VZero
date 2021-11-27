import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from enum import IntEnum
from nutil.vars import AutoIntEnum, normalize, nsign_str
from logic.mechanics.common import *


def str2item(name):
    return getattr(ITEM, name.upper().replace(' ', '_'))


ITEM = AutoIntEnum('ITEM', [
    # Basic
    'BOOTS',
    'SLIPPERS',
    'STONKS',
    # Herbal
    'BRANCH',
    'LEAF',
    'TRUNK',
    # Ornaments
    'AMULET',
    # Potions
    'HEART',
    'VIAL',
    'GEM',
])
ITEM_LIST = [item for item in ITEM]
ICAT = ITEM_CATEGORIES = IntEnum('ITEM_CATEGORIES', [
    'BASIC',
    'HERBAL',
    'ORNAMENT',
    'POTION',
])
ICAT_COLORS = [
    (0.5, 0.5, 0),
    (0.5, 1, 0.25),
    (0, 0.5, 0.5),
    (1, 0, 0.5),
]

class ItemData:
    def __init__(self, category, cost, stats=None):
        self.category = category
        self.cost = cost
        self.stats = stats if stats is not None else {}

ITEM_STATS = {
    # Basic
    ITEM.BOOTS: ItemData(ICAT.BASIC, 120, {STAT.AIR: {VALUE.CURRENT: 8}, STAT.EARTH: {VALUE.CURRENT: 5}}),
    ITEM.SLIPPERS: ItemData(ICAT.BASIC, 155, {STAT.AIR: {VALUE.CURRENT: 12}, STAT.MANA: {VALUE.MAX_VALUE: 5}}),
    ITEM.STONKS: ItemData(ICAT.BASIC, 100, {STAT.GOLD: {VALUE.DELTA: 0.003}}),
    # Herbal
    ITEM.BRANCH: ItemData(ICAT.HERBAL, 85, {STAT.PHYSICAL: {VALUE.CURRENT: 4}, STAT.EARTH: {VALUE.CURRENT: 12}}),
    ITEM.LEAF: ItemData(ICAT.HERBAL, 125, {STAT.FIRE: {VALUE.CURRENT: 10}, STAT.WATER: {VALUE.CURRENT: 10}}),
    ITEM.TRUNK: ItemData(ICAT.HERBAL, 215, {STAT.EARTH: {VALUE.CURRENT: 16}, STAT.FIRE: {VALUE.CURRENT: 16}}),
    # Ornaments
    ITEM.AMULET: ItemData(ICAT.ORNAMENT, 260, {STAT.PHYSICAL: {VALUE.CURRENT: 22}, STAT.FIRE: {VALUE.CURRENT: 16}}),
    # Potions
    ITEM.HEART: ItemData(ICAT.POTION, 225, {STAT.HP: {VALUE.DELTA: 0.003, VALUE.MAX_VALUE: 30}}),
    ITEM.VIAL: ItemData(ICAT.POTION, 165, {STAT.MANA: {VALUE.DELTA: 0.002, VALUE.MAX_VALUE: 20}}),
    ITEM.GEM: ItemData(ICAT.POTION, 130, {STAT.WATER: {VALUE.CURRENT: 10}, STAT.HP: {VALUE.MAX_VALUE: 10}}),
}


def item_repr(item):
    name = item.name.lower().capitalize().replace('_', ' ')
    cost = ITEM_STATS[item].cost
    s = []
    for stat, values in ITEM_STATS[item].stats.items():
        v = []
        for value_name, value in values.items():
            value_name = '' if value_name is VALUE.CURRENT else f' {value_name.name.lower()}'
            if '_' in value_name:
                value_name = value_name.split('_')[0]
            elif value_name == 'delta':
                value = self.api.s2ticks(value)
                value_name = '/s'
            value = f'{nsign_str(value)}'
            v.append(f'{value}{value_name}')
        stat_name = stat.name.lower().capitalize().replace('_', ' ')
        s.append(f'{stat_name}: {", ".join(v)}')
    nl = "\n"
    category = ITEM_STATS[item].category.name.lower().capitalize()
    r = '\n'.join([
        name,
        f'Shop: {category}',
        f'{cost} gold\n',
        *s,
    ])
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
