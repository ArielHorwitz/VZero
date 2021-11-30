import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np

from nutil.vars import collide_point
from nutil.random import SEED
from data import resource_name
from data.load import RDF

from logic.mechanics import import_mod_module
from logic.mechanics.mod import ModEncounterAPI
from logic.mechanics.player import Player
from logic.mechanics.common import *
MapGenerator = import_mod_module('mapgen').MapGenerator
abilities = import_mod_module('abilities._release')
units = import_mod_module('units.units')
items = import_mod_module('items.items')


ABILITY_CLASSES = abilities.ABILITY_CLASSES


UNIT_CLASSES = {
    'player': units.Player,
    'creep': units.Creep,
    'camper': units.Camper,
    'treasure': units.Treasure,
    'shopkeeper': units.Shopkeeper,
    'fountain': units.Fountain,
    'dps_meter': units.DPSMeter,
}


def get_default_stats():
    table = np.zeros(shape=(len(STAT), len(VALUE)))
    LARGE_ENOUGH = 1_000_000_000
    table[:, VALUE.CURRENT] = 0
    table[:, VALUE.DELTA] = 0
    table[:, VALUE.TARGET_VALUE] = -LARGE_ENOUGH
    table[:, VALUE.MIN_VALUE] = 0
    table[:, VALUE.MAX_VALUE] = LARGE_ENOUGH

    table[(STAT.POS_X, STAT.POS_Y), VALUE.MIN_VALUE] = -LARGE_ENOUGH
    table[STAT.WEIGHT, VALUE.MIN_VALUE] = -1
    table[STAT.HITBOX, VALUE.CURRENT] = 100
    table[STAT.HP, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.HP, VALUE.TARGET_VALUE] = 0
    table[STAT.MANA, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.MANA, VALUE.MAX_VALUE] = 20

    ELEMENTAL_STATS = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER]
    table[ELEMENTAL_STATS, VALUE.CURRENT] = 10
    table[ELEMENTAL_STATS, VALUE.MIN_VALUE] = 2
    return table


logger.debug(f'Default stats:\n{get_default_stats()}')




class API(ModEncounterAPI):
    RNG = np.random.default_rng()

    def __init__(self, api):
        self.api = api
        # Load unit types from config file
        self.unit_types = self.__load_unit_types()
        self.player_stats = self.unit_types['player']['stats']
        self.player_class = units.Player
        # Generate map
        self.map = MapGenerator(self.api, self.unit_types)
        set_spawn_location(self.player_stats, self.map.player_spawn)

    # Map
    @property
    def map_size(self):
        return self.map.size

    @property
    def map_image_source(self):
        return self.map.image

    @property
    def request_redraw(self):
        return self.map.request_redraw

    def spawn_map(self):
        return self.map.spawn_map()

    # Unit spawn
    def __load_unit_types(self):
        raw_data = RDF.load(RDF.CONFIG_DIR / 'units.rdf')
        units = {}
        for unit_name, unit_data in raw_data.items():
            internal_name = resource_name(unit_name)
            if internal_name in units:
                m = f'Unit name duplication: {internal_name}'
                logger.critical(m)
                raise ValueError(m)
            unit_cls_name = unit_data[0][0][0]
            unit_cls = UNIT_CLASSES[unit_cls_name]
            raw_stats = unit_data['stats']
            setup_params = unit_data[0]
            del setup_params[0]
            stats = self.__load_raw_stats(raw_stats)
            logger.info(f'Loaded unit type: {unit_name} ({unit_cls_name} - {unit_cls}). setup params: {setup_params}')
            units[internal_name] = {
                'cls': unit_cls,
                'name': unit_name,
                'stats': stats,
                'setup_params': setup_params,
            }
        return units

    @staticmethod
    def __load_raw_stats(raw_stats):
        stats = get_default_stats()
        modified_stats = []
        for stat_and_value, raw_value in raw_stats.items():
            if stat_and_value == 0:
                continue
            value_name = 'current'
            if '.' in stat_and_value:
                stat_name, value_name = stat_and_value.split('.')
            else:
                stat_name = stat_and_value
            stat_ = str2stat(stat_name)
            value_ = str2value(value_name)
            stats[stat_][value_] = float(raw_value)
            modified_stats.append(f'{stat_.name}.{value_.name}: {raw_value}')
        logger.debug(f'Loaded raw stats: {", ".join(modified_stats)}')
        return stats

    # Reactions
    def hp_zero(self, uid):
        unit = self.api.units[uid]
        logger.debug(f'Unit {unit.name} died')
        self.api.units[uid].hp_zero()

    def status_zero(self, uid, status):
        unit = self.api.units[uid]
        status = list(STATUS)[status]
        logger.debug(f'Unit {unit.name} lost status {status.name}')
        self.api.units[uid].status_zero(status)

    # GUI Agent panel
    def agent_panel_bars(self, uid):
        hp = self.api.get_stats(uid, STAT.HP)
        max_hp = self.api.get_stats(uid, STAT.HP, value_name=VALUE.MAX_VALUE)
        mana = self.api.get_stats(uid, STAT.MANA)
        max_mana = self.api.get_stats(uid, STAT.MANA, value_name=VALUE.MAX_VALUE)
        return [
            (hp/max_hp, (1, 0, 0), f'HP: {hp:.1f}/{max_hp:.1f}'),
            (mana/max_mana, (0, 0, 1), f'Mana: {mana:.1f}/{max_mana:.1f}'),
        ]

    def agent_panel_boxes_labels(self, uid):
        stats = self.api.get_stats(uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
            STAT.AIR, STAT.WATER, STAT.GOLD,
        ])
        return tuple(f'{_:.1f}' for _ in stats)

    def agent_panel_boxes_sprites(self, uid):
        return [
            ('ability', 'physical'),
            ('ability', 'fire'),
            ('ability', 'earth'),
            ('ability', 'air'),
            ('ability', 'water'),
            ('ability', 'gold'),
        ]

    def agent_panel_label(self, uid):
        dist = math.dist(self.api.get_position(0), self.api.get_position(uid))
        v = self.api.s2ticks(self.api.get_velocity(uid))
        return '\n'.join([
            f'Speed: {v:.1f}',
            f'Distance: {dist:.1f}',
            '',
            self.api.pretty_statuses(uid),
        ])

    # GUI Shop (menu)
    menu_title = 'Shop'
    menu_texts = [f'{items.item_repr(item)}' for item in items.ITEM]
    item_colors = [items.ICAT_COLORS[items.ITEM_STATS[item].category-1] for item in items.ITEM]
    def menu_click(self, index, right_click):
        logger.debug(f'Menu click on {index} (right_click: {right_click})')
        if right_click:
            r = items.Shop.buy_item(self.api, 0, index)
            if not isinstance(r, FAIL_RESULT):
                return 'ability', 'shop'
        return 'ui', 'target'

    @property
    def menu_colors(self):
        colors = []
        for i, color in enumerate(self.item_colors):
            colors.append((*color, 1) if all([
                self.active_shop_items[i],
                items.Shop.check_cost(self.api, 0, items.ITEM_LIST[i]),
            ]) else (*color, 0.1))
        return colors

    @property
    def active_shop_items(self):
        item_categories = np.array([items.ITEM_STATS[item].category.value for item in items.ITEM])
        active_category = self.api.get_status(0, STATUS.SHOP)
        active_items = item_categories == active_category
        return active_items

def set_spawn_location(stats, spawn):
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.CURRENT] = spawn
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.TARGET_VALUE] = spawn

EncounterAPI = API
