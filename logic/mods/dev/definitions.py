import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import copy, random
import numpy as np
from collections import defaultdict
from nutil.vars import NP
from nutil.random import SEED
from data import resource_name
from data.load import RDF
from data.tileset import TileMap
from logic.mechanics import import_mod_module
from logic.mechanics.mod import ModEncounterAPI
from logic.mechanics.player import Player
from logic.mechanics.common import *
abilities = import_mod_module('abilities._release')
units = import_mod_module('units.units')
items = import_mod_module('items.items')


ABILITY_CLASSES = abilities.ABILITY_CLASSES


UNIT_CLASSES = {
    'player': Player,
    'camper': units.Camper,
    'roamer': units.Roamer,
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
    table[STAT.HITBOX, VALUE.CURRENT] = 50
    table[STAT.HP, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.HP, VALUE.TARGET_VALUE] = 0
    table[STAT.MANA, VALUE.CURRENT] = LARGE_ENOUGH

    ELEMENTAL_STATS = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER]
    table[ELEMENTAL_STATS, VALUE.CURRENT] = 10
    table[ELEMENTAL_STATS, VALUE.MIN_VALUE] = 2
    return table


logger.debug(f'Default stats:\n{get_default_stats()}')


class API(ModEncounterAPI):
    RNG = np.random.default_rng()
    TERRITORY_SIZE = 1000
    SPAWN_MULTIPLIER = 3
    menu_title = 'Shop'
    menu_texts = [f'{items.item_repr(item)}' for item in items.ITEM]

    def __init__(self, api):
        self.api = api
        self.map_size = np.full(2, 10_000)
        # Load unit types from config file
        self.unit_types = self.__load_unit_types()
        self.player_stats = self.unit_types['player']['stats']
        set_spawn_location(self.player_stats, (self.map_size/2))
        self.map_image_source = TileMap(['tiles1']).make_map(100, 100)

    # Map generation
    def spawn_map(self):
        territory_types = RDF(RDF.CONFIG_DIR / 'map.rdf')
        territories = self.get_territories()
        for ttype, location in territories:
            camps = territory_types[ttype]
            camp_names = tuple(camps.keys())
            camp_name = random.choice(camp_names)
            logger.debug(f'Chose camp: {camp_name} from options: {camp_names}')
            isolate = 'isolate' in camps[camp_name].positional
            spawn = self.random_offset_in_territory(location)
            for utype, amount in camps[camp_name].items():
                for i in range(int(amount)):
                    if isolate:
                        spawn = self.random_offset_in_territory(location)
                    self.add_unit(utype, spawn)

    def get_territories(self):
        territories = [
            ('Spawn', np.array([5000, 5000])),
            *self.get_territories_quadrant(),
            *self.get_territories_quadrant(flipx=True),
            *self.get_territories_quadrant(flipx=False, flipy=True),
            *self.get_territories_quadrant(flipx=True, flipy=True),
        ]
        return territories

    def get_territories_quadrant(self, flipx=False, flipy=False, offset=None):
        def territory_offset(x, y):
            return np.array([x*self.TERRITORY_SIZE+self.TERRITORY_SIZE/2,
                             y*self.TERRITORY_SIZE+self.TERRITORY_SIZE/2])
        if offset is None:
            offset = self.map_size/2
        sx = -1 if flipx else 1
        sy = -1 if flipy else 1
        TIER1_NEUTRALS = 2
        TIER2_NEUTRALS = 2
        TIER3_NEUTRALS = 1
        neutrals = {
            # Tier 1
            *[SEED.choice([(2, 0), (3, 0), (4, 0), (0, 2), (0, 3), (0, 4)]) for _ in range(TIER1_NEUTRALS)],
            # Tier 2
            *[SEED.choice([(3, 1), (4, 1), (1, 3), (1, 4)]) for _ in range(TIER2_NEUTRALS)],
            # Tier 3
            *[SEED.choice([(4, 2), (2, 4)]) for _ in range(TIER3_NEUTRALS)],
        }
        logger.debug(f'Chose neutrals: {neutrals}')
        t = []
        for x in range(5):
            for y in range(5):
                if x == y == 0: continue
                for tier in range(5):
                    if x == tier or y == tier:
                        camp = f'Neutral {tier+1}' if (x, y) in neutrals else f'Monsters {tier+1}'
                        break
                location = territory_offset(x, y) * (sx, sy) + offset
                t.append((camp, location))
        return t

    def random_offset_in_territory(self, location):
        return location + self.RNG.random(2) * self.TERRITORY_SIZE - (self.TERRITORY_SIZE/2)

    # Unit spawn
    def add_unit(self, unit_type, spawn):
        internal_name = resource_name(unit_type)
        unit_data = self.unit_types[internal_name]
        unit_cls = unit_data['cls']
        name = copy.deepcopy(unit_data['name'])
        stats = unit_data['stats']
        set_spawn_location(stats, spawn)
        setup_params = copy.deepcopy(unit_data['setup_params'])
        unit = self.api.add_unit(unit_cls, name, stats, setup_params)
        logger.debug(f'Mod created new unit {internal_name} with uid {unit.uid} and setup_params: {setup_params}')
        return unit

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

    # Shop (mod menu)
    def menu_click(self, index, right_click):
        logger.debug(f'Menu click on {index} (right_click: {right_click})')
        if right_click:
            r = items.Shop.buy_item(self.api, 0, index)
            if not isinstance(r, FAIL_RESULT):
                return 'ability', 'shop'
        return 'ui', 'target'

    @property
    def menu_colors(self):
        return [(0.2, 0.2, 0.2) if a else (0, 0, 0) for a in self.active_shop_items]

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
