import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import numpy as np
from nutil.file import file_load
from nutil.random import h256
from nutil.vars import AutoIntEnum
from data import VERSION, resource_name
from data.load import RDF
from engine.common import *
from logic.abilities import ABILITY_CLASSES



# Abilities
def _load_abilities():
    raw_data = RDF(RDF.CONFIG_DIR / 'abilities.rdf')
    raw_items = tuple(raw_data.items())
    abilities = []
    for aid in ABILITY:
        name, raw_data = raw_items[aid]
        if 'type' not in raw_data.default:
            raise CorruptedDataError(f'Ability {aid.name} missing a type.')
        ability_cls = ABILITY_CLASSES[raw_data.default['type']]
        ability = ability_cls(aid, name, raw_data)
        assert len(abilities) == aid
        abilities.append(ability)
        logger.info(f'Loaded ability: {ability}')
    for ability in abilities:
        ability._setup()
    return abilities

ABILITIES = _load_abilities()


# Units
from logic.units import UNIT_CLASSES


def _get_default_stats():
    table = np.zeros(shape=(len(STAT), len(VALUE)))
    LARGE_ENOUGH = 1_000_000_000
    table[:, VALUE.CURRENT] = 0
    table[:, VALUE.DELTA] = 0
    table[:, VALUE.TARGET] = -LARGE_ENOUGH
    table[:, VALUE.MIN] = 0
    table[:, VALUE.MAX] = LARGE_ENOUGH

    table[STAT.ALLEGIANCE, VALUE.MIN] = -LARGE_ENOUGH
    table[STAT.ALLEGIANCE, VALUE.CURRENT] = 1
    table[(STAT.POS_X, STAT.POS_Y), VALUE.MIN] = -LARGE_ENOUGH
    table[STAT.WEIGHT, VALUE.MIN] = -1
    table[STAT.HITBOX, VALUE.CURRENT] = 100
    table[STAT.HP, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.HP, VALUE.TARGET] = 0
    table[STAT.MANA, VALUE.CURRENT] = LARGE_ENOUGH
    table[STAT.MANA, VALUE.MAX] = 20

    ELEMENTAL_STATS = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER]
    table[ELEMENTAL_STATS, VALUE.CURRENT] = 1
    table[ELEMENTAL_STATS, VALUE.MIN] = 1
    return table

def _load_raw_stats(raw_stats):
    stats = _get_default_stats()
    modified_stats = []
    for raw_key, raw_value in raw_stats.items():
        value_name = 'current'
        if '.' in raw_key:
            stat_name, value_name = raw_key.split('.')
        else:
            stat_name = raw_key
        stat_ = str2stat(stat_name)
        value_ = str2value(value_name)
        stats[stat_][value_] = float(raw_value)
        modified_stats.append(f'{stat_.name}.{value_.name}: {raw_value}')
    logger.debug(f'Loaded raw stats: {", ".join(modified_stats)}')
    return stats

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

def set_spawn_location(stats, spawn):
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.CURRENT] = spawn
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.TARGET] = spawn

logger.debug(f'Default stats:\n{_get_default_stats()}')

RAW_UNITS = _load_unit_types()


metagame_data = str(VERSION).join(file_load(RDF.CONFIG_DIR / f'{_}.rdf') for _ in ('abilities', 'items', 'units', 'map', 'spawn_types'))
METAGAME_BALANCE = h256(metagame_data)
METAGAME_BALANCE_SHORT = METAGAME_BALANCE[:4]
logger.info(f'Metagame Balance: {METAGAME_BALANCE_SHORT} ({METAGAME_BALANCE})')
