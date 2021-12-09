import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from collections import defaultdict
from enum import IntEnum
from data.load import RDF
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

ITEM = AutoIntEnum('ITEM', [internal_name(name) for name in RDF(RDF.CONFIG_DIR / 'items.rdf').keys()])


class Item:
    def __init__(self, iid, name, raw_data):
        self.iid = iid
        self.name = name

        self.category = getattr(ICAT, raw_data.default['category'].upper())
        self.color = CATEGORY_COLORS[self.category]
        self.cost = raw_data.default['cost']
        self.sell_multi = 0.5
        self.aid = None
        self.ability = None
        if 'ability' in raw_data.default:
            self.aid = str2ability(raw_data.default['ability'])
            self.ability = ABILITIES[self.aid]

        self.stats = {}
        if 'stats' in raw_data:
            self.stats = _load_raw_stats(raw_data['stats'])

        stat_str = []
        for stat in self.stats:
            for value_name in self.stats[stat]:
                sname = stat.name.lower().capitalize()
                value = self.stats[stat][value_name]
                if value_name is VALUE.DELTA:
                    value = f'{nsign_str(round(value * 120, 5))} / s'
                else:
                    value = nsign_str(value)
                    # TODO remove hardcoded tick2s calculation
                if value_name is not VALUE.CURRENT:
                    f'{value_name.name.lower().capitalize()} {sname}'
                stat_str.append(f'{sname}: {value}')

        self.shop_text = f'{self.name} - {round(self.cost)} ({self.category.name.lower().capitalize()})', '\n'.join([
            *stat_str,
            f'> {self.ability.universal_description}' if self.ability is not None else '',
        ])

    def check_shop(self, engine, uid):
        unit = engine.units[uid]
        icat = round(engine.get_status(uid, STATUS.SHOP))
        if icat != self.category.value or None not in unit.item_slots:
            return False
        return True

    def check_buy(self, engine, uid):
        unit = engine.units[uid]
        icat = round(engine.get_status(uid, STATUS.SHOP))
        if icat != self.category.value or None not in unit.item_slots:
            return FAIL_RESULT.MISSING_TARGET

        if self.iid in unit.item_slots:
            return FAIL_RESULT.ON_COOLDOWN

        if not engine.get_stats(uid, STAT.GOLD) >= self.cost:
            return FAIL_RESULT.MISSING_COST

        return True

    def gui_state(self, api, uid, target=None):
        if self.ability is not None:
            return self.ability.gui_state(api, uid, target)
        return '', (0, 0.9, 0, 1)

    def quickcast(self, api, uid, target):
        if self.aid is None:
            return
        r = api.abilities[self.aid].cast(api.engine, uid, target)
        return r

    def buy_item(self, engine, uid):
        r = self.check_buy(engine, uid)
        if isinstance(r, FAIL_RESULT):
            return r

        unit = engine.units[uid]
        for index in range(6):
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
        engine.set_stats(uid, STAT.GOLD, self.cost*self.sell_multi, additive=True)
        for stat_name, stat in self.stats.items():
            for value_name, value in stat.items():
                engine.set_stats(uid, stat_name, -value, value_name=value_name, additive=True)

        result = self.iid

        logger.debug(f'{unit.name} sold item: {self.name}')
        return result

    def __repr__(self):
        return f'<Item {self.iid} {self.name}>'


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
    raw_items = tuple(RDF(RDF.CONFIG_DIR / 'items.rdf').items())
    items = []
    for iid in ITEM:
        name, raw_data = raw_items[iid]
        item = Item(iid, name, raw_data)
        logger.info(f'Loaded item: {item}')
        items.append(item)
    return items

ITEMS = _load_items()
