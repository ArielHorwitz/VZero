import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from collections import defaultdict
from enum import IntEnum
from data.load import RDF
from data.settings import Settings
from nutil.vars import AutoIntEnum, nsign_str
from engine.common import *
from logic.data import ABILITIES


ICAT = ITEM_CATEGORIES = IntEnum('ITEM_CATEGORIES', [
    'BASIC',
    'HERBAL',
    'POTION',
    'ORNAMENT',
])
CATEGORY_COLORS = {
    ICAT.BASIC: (0.5, 0.5, 0),
    ICAT.HERBAL: (0.1, 0.7, 0.05),
    ICAT.POTION: (0.7, 0, 0.4),
    ICAT.ORNAMENT: (0, 0.5, 0.5),
}
SELL_MULTIPLIER = 0.8
QUICK_RESELL_WINDOW = 1000

ALL_ITEM_NAMES = list(RDF(RDF.CONFIG_DIR / 'items.rdf').keys())
di = Settings.get_setting('dev_items', 'General')
if di == 0:
    logger.info(f'Skipping dev items')
    ALL_ITEM_NAMES = list(filter(lambda x: not x.lower().startswith('dev '), ALL_ITEM_NAMES))
ITEM = AutoIntEnum('ITEM', [internal_name(name) for name in ALL_ITEM_NAMES])


class Item:
    def __init__(self, iid, name, raw_data):
        self.iid = iid
        self.name = name

        self.category = getattr(ICAT, raw_data.default['category'].upper())
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

    def shop_text(self, engine, uid):
        stat_str = []
        for stat in self.stats:
            for value_name in self.stats[stat]:
                sname = stat.name.lower().capitalize()
                value = self.stats[stat][value_name]
                if value_name is VALUE.DELTA:
                    value = f'{nsign_str(round(engine.s2ticks(value), 5))}/s'
                else:
                    value = nsign_str(value)
                    if value_name is not VALUE.CURRENT:
                        sname = f'{value_name.name.lower().capitalize()} {sname.lower()}'
                stat_str.append(f'{sname}: {value}')
        return '\n'.join([
            *stat_str,
            f'\n{self.ability.name}: {self.ability.description(engine, uid)}' if self.ability is not None else '',
        ])

    def check_shop(self, engine, uid):
        unit = engine.units[uid]
        icat = round(engine.get_status(uid, STATUS.SHOP))
        if icat != self.category.value or None not in unit.item_slots:
            return False
        return True

    def check_buy(self, engine, uid):
        unit = engine.units[uid]

        if self.iid in unit.item_slots:
            return FAIL_RESULT.ON_COOLDOWN

        icat = round(engine.get_status(uid, STATUS.SHOP))
        if icat != self.category.value:
            return FAIL_RESULT.OUT_OF_RANGE

        if None not in unit.item_slots:
            return FAIL_RESULT.MISSING_TARGET

        if not engine.get_stats(uid, STAT.GOLD) >= self.cost:
            return FAIL_RESULT.MISSING_COST

        return True

    def gui_state(self, api, uid, target=None):
        if self.ability is not None:
            return self.ability.gui_state(api, uid, target)
        return '', (0, 0, 0, 0)

    def cast(self, api, uid, target):
        if self.aid is None:
            return FAIL_RESULT.MISSING_ACTIVE
        r = api.abilities[self.aid].cast(api.engine, uid, target)
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
        for index in range(len(unit.item_slots)):
            if unit.item_slots[index] is None:
                unit.item_slots[index] = self.iid
                break
        else:
            raise RuntimeError(f'Failed to find empty item slot. This should not happen')

        engine.set_stats(uid, STAT.GOLD, -self.cost, additive=True)
        for stat_name, stat in self.stats.items():
            for value_name, value in stat.items():
                engine.set_stats(uid, stat_name, value, value_name=value_name, additive=True)
        result = self.iid
        logger.debug(f'{unit.name} bought item: {self.name}')
        engine.units[uid].cache[f'{self}-buy'] = engine.tick
        return result

    def sell_item(self, engine, uid):
        unit = engine.units[uid]
        assert self.iid in unit.item_slots
        index = unit.item_slots.index(self.iid)

        icat = round(engine.get_status(uid, STATUS.SHOP))
        if icat == 0:
            logger.debug(f'{unit.name} missing shop status to sell')
            return FAIL_RESULT.MISSING_TARGET

        unit.item_slots[index] = None
        buy_tick = engine.units[uid].cache[f'{self}-buy']
        sell_multi = 1 if engine.tick - buy_tick < QUICK_RESELL_WINDOW else self.sell_multi
        engine.set_stats(uid, STAT.GOLD, self.cost*sell_multi, additive=True)
        for stat_name, stat in self.stats.items():
            for value_name, value in stat.items():
                engine.set_stats(uid, stat_name, -value, value_name=value_name, additive=True)

        result = self.iid

        logger.debug(f'{unit.name} sold item: {self.name}')
        return result

    def __repr__(self):
        return f'<Item {self.iid} {self.name}>'

    @staticmethod
    def item_category_gui(icat):
        icat = round(icat)
        if 0 < icat <= len(ITEM_CATEGORIES):
            icat = list(ITEM_CATEGORIES)[icat-1]
            shop_name = icat.name.lower().capitalize()
            shop_color = CATEGORY_COLORS[icat]
            return shop_name, shop_color
        return None, None


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
        logger.info(f'Loaded item: {item}')
        items.append(item)
    return items




ITEMS = _load_items()
