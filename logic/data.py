import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import numpy as np
from data import resource_name
from data.load import RDF
from engine.common import *
from logic.abilities import ABILITY_CLASSES
from logic.units import UNIT_CLASSES


class CorruptedDataError(Exception):
    pass


# Abilities
def __load_abilities():
    raw_data = RDF(RDF.CONFIG_DIR / 'abilities.rdf')
    raw_items = tuple(raw_data.items())
    abilities = []
    for aid in ABILITY:
        name, raw_data = raw_items[aid]
        if 'type' not in raw_data.default:
            raise CorruptedDataError(f'Ability {aid.name} missing a type.')
        ability_cls = ABILITY_CLASSES[raw_data.default['type']]
        color = str2color(raw_data.default['color']) if 'color' in raw_data.default else (0.5,0.5,0.5)
        stats = raw_data['stats'] if 'stats' in raw_data else {}
        ability = ability_cls(aid, name, color, stats)
        assert len(abilities) == aid
        abilities.append(ability)
        logger.info(f'Loaded ability: {ability} - with params: {stats}')
    return abilities


ABILITIES = __load_abilities()


# Items
ITEM_STATS = []


# Units
def _load_unit_types():
    raw_data = RDF(RDF.CONFIG_DIR / 'units.rdf')
    units = {}
    for unit_name, unit_data in raw_data.items():
        internal_name = resource_name(unit_name)
        if internal_name in units:
            m = f'Unit name duplication: {internal_name}'
            logger.critical(m)
            raise ValueError(m)
        if 'type' not in unit_data.default:
            raise CorruptedDataError(f'Unit {unit_name} missing a type.')
        unit_cls_name = unit_data.default['type']
        unit_cls = UNIT_CLASSES[unit_cls_name]

        raw_stats = {}
        if 'stats' in unit_data:
            raw_stats = unit_data['stats']
        stats = _load_raw_stats(raw_stats)

        params = unit_data.default
        del params['type']

        units[internal_name] = {
            'name': unit_name,
            'cls': unit_cls,
            'params': params,
            'stats': stats,
        }
        logger.info(f'Loaded unit type: {unit_name} - {unit_cls_name}. Params: {params}')
    return units

def _load_raw_stats(raw_stats):
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

def set_spawn_location(stats, spawn):
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.CURRENT] = spawn
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.TARGET] = spawn

def get_default_stats():
    table = np.zeros(shape=(len(STAT), len(VALUE)))
    LARGE_ENOUGH = 1_000_000_000
    table[:, VALUE.CURRENT] = 0
    table[:, VALUE.DELTA] = 0
    table[:, VALUE.TARGET] = -LARGE_ENOUGH
    table[:, VALUE.MIN] = 0
    table[:, VALUE.MAX] = LARGE_ENOUGH

    table[(STAT.POS_X, STAT.POS_Y), VALUE.MIN] = -LARGE_ENOUGH
    table[STAT.WEIGHT, VALUE.MIN] = -1
    table[STAT.HITBOX, VALUE.CURRENT] = 100
    table[STAT.HP, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.HP, VALUE.TARGET] = 0
    table[STAT.MANA, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.MANA, VALUE.MAX] = 20

    ELEMENTAL_STATS = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER]
    table[ELEMENTAL_STATS, VALUE.CURRENT] = 10
    table[ELEMENTAL_STATS, VALUE.MIN] = 2
    return table

logger.debug(f'Default stats:\n{get_default_stats()}')

RAW_UNITS = _load_unit_types()
