import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
from collections import defaultdict
from enum import IntEnum
from data import DEV_BUILD
from data.load import RDF
from data.assets import Assets
from data.settings import Settings
from nutil.vars import AutoIntEnum, nsign_str
from logic.common import *
from logic.abilities import ABILITIES
from logic.mechanics import Mechanics


ITEM_CATEGORIES = IntEnum('ITEM_CATEGORIES', [
    'BASIC',
    'HERBAL',
    'ORNAMENT',
    # 'POTION',
])
logger.debug(f'Set Item Categories: {tuple(f"{_.name} {_.value}" for _ in ITEM_CATEGORIES)}')
CATEGORY_COLORS = {
    ITEM_CATEGORIES.BASIC: (0.5, 0.5, 0),
    ITEM_CATEGORIES.HERBAL: (0.1, 0.7, 0.05),
    ITEM_CATEGORIES.ORNAMENT: (0, 0.5, 0.5),
    # ITEM_CATEGORIES.POTION: (0.7, 0, 0.4),
}
assert all([icat in CATEGORY_COLORS for icat in ITEM_CATEGORIES])
SELL_MULTIPLIER = 0.8
QUICK_RESELL_WINDOW = 1000

ALL_ITEM_NAMES = list(RDF(RDF.CONFIG_DIR / 'items.rdf').keys())
if not DEV_BUILD:
    logger.info(f'Skipping dev items')
    ALL_ITEM_NAMES = list(filter(lambda x: not x.lower().startswith('dev '), ALL_ITEM_NAMES))
ITEM = AutoIntEnum('ITEM', [internal_name(name) for name in ALL_ITEM_NAMES])


class Item:
    def __init__(self, iid, name, raw_data):
        self.iid = iid
        self.name = name
        self.sprite = Assets.get_sprite('ability', raw_data.default['sprite'] if 'sprite' in raw_data.default else self.name)
        self.category = getattr(ITEM_CATEGORIES, raw_data.default['category'].upper())
        self.color = CATEGORY_COLORS[self.category]
        self.cost = raw_data.default['cost']
        self.sell_multi = SELL_MULTIPLIER
        self.aid = None
        self.ability = None
        if 'ability' in raw_data.default:
            self.aid = str2ability(raw_data.default['ability'])
            self.ability = ABILITIES[self.aid]
        elif hasattr(ABILITY, internal_name(self.name).upper()):
            self.aid = str2ability(self.name)
            self.ability = ABILITIES[self.aid]

        self.stats = {}
        if 'stats' in raw_data:
            self.stats = _load_raw_stats(raw_data['stats'])
        self.shop_name = f'{self.name}\n{round(self.cost)} ({self.category.name.lower().capitalize()})'
        logger.info(f'Created item: {self} from raw_data: {raw_data}')

    def shop_text(self, engine, uid):
        stat_str = []
        for stat in self.stats:
            for value_name in self.stats[stat]:
                sname = stat.name.lower().capitalize()
                value = self.stats[stat][value_name]
                if value_name is VALUE.DELTA:
                    value = f'{nsign_str(round(s2ticks(value), 5))}/s'
                else:
                    value = nsign_str(value)
                    if value_name is not VALUE.CURRENT:
                        sname = f'{value_name.name.lower().capitalize()} {sname.lower()}'
                stat_str.append(f'{sname}: {value}')
        return '\n'.join([
            *stat_str,
            f'\n{self.ability.description(engine, uid)}' if self.ability is not None else '',
        ])

    def check_buy(self, engine, uid):
        unit = engine.units[uid]
        # Check duplicates
        if self.iid in unit.item_slots:
            return FAIL_RESULT.ON_COOLDOWN
        # Check shop stat
        icat = round(Mechanics.get_status(engine, uid, STAT.SHOP))
        if icat < self.category.value:
            return FAIL_RESULT.OUT_OF_RANGE
        # Check slots
        if unit.empty_item_slots == 0:
            return FAIL_RESULT.MISSING_TARGET
        # Check cost
        if not engine.get_stats(uid, STAT.GOLD) >= self.cost:
            return FAIL_RESULT.MISSING_COST
        return True

    def gui_state(self, api, uid, target=None):
        if self.ability is not None:
            return self.ability.gui_state(api, uid)
        return '', (0, 0, 0, 0)

    def active(self, api, uid, target, alt=0):
        if self.aid is None:
            return FAIL_RESULT.MISSING_ACTIVE
        r = api.abilities[self.aid].active(api.engine, uid, target, alt)
        return r

    def passive(self, api, uid, dt):
        if self.aid is None:
            return
        r = ABILITIES[self.aid].passive(api, uid, dt)
        return r

    def buy_item(self, engine, uid):
        r = self.check_buy(engine, uid)
        if isinstance(r, FAIL_RESULT):
            return r
        unit = engine.units[uid]
        assert unit.empty_item_slots > 0
        unit.add_item(self.iid)

        engine.set_stats(uid, STAT.GOLD, -self.cost, additive=True)
        for stat_name, stat in self.stats.items():
            for value_name, value in stat.items():
                engine.set_stats(uid, stat_name, value, value_name=value_name, additive=True)
        result = self.iid
        logger.info(f'{unit.name} bought item: {self}')
        engine.units[uid].cache[f'{self}-buy'] = engine.tick
        return result

    def sell_item(self, engine, uid):
        unit = engine.units[uid]
        assert self.iid in unit.items

        icat = round(Mechanics.get_status(engine, uid, STAT.SHOP))
        if icat < 1:
            logger.debug(f'{unit.name} missing shop status to sell')
            return FAIL_RESULT.MISSING_TARGET

        unit.remove_item(self.iid)

        buy_tick = engine.units[uid].cache[f'{self}-buy']
        sell_multi = 1 if engine.tick - buy_tick < QUICK_RESELL_WINDOW else self.sell_multi
        engine.set_stats(uid, STAT.GOLD, self.cost*sell_multi, additive=True)
        for stat_name, stat in self.stats.items():
            for value_name, value in stat.items():
                engine.set_stats(uid, stat_name, -value, value_name=value_name, additive=True)

        result = self.iid

        logger.info(f'{unit.name} sold item: {self}')
        return result

    def __repr__(self):
        return f'<Item {self.iid} {self.name}>'

    @classmethod
    def item_category_gui(cls, stat):
        icat = cls.stat2category(stat)
        if icat is not None:
            return icat.name.lower(), CATEGORY_COLORS[icat]
        return None, None

    @staticmethod
    def stat2category(stat):
        if stat < 1:
            return None
        catindex = min(math.floor(stat), len(ITEM_CATEGORIES)) - 1
        return list(ITEM_CATEGORIES)[catindex]


def _load_raw_stats(raw_stats):
    stats = defaultdict(lambda: {})
    for raw_key, raw_value in raw_stats.items():
        value_name = 'current'
        if '.' in raw_key:
            stat_name, value_name = raw_key.split('.')
        else:
            stat_name = raw_key
        stat_ = str2stat(stat_name)
        value_ = str2value(value_name)
        stats[stat_][value_] = float(raw_value)
    return dict(stats)


def _load_items():
    raw_items = RDF(RDF.CONFIG_DIR / 'items.rdf')
    items = []
    for iid in ITEM:
        name = ALL_ITEM_NAMES[iid]
        raw_data = raw_items[name]
        item = Item(iid, name, raw_data)
        items.append(item)
    logger.info(f'Loaded {len(items)} items.')
    return items


ITEMS = _load_items()
