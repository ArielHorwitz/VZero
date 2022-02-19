import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import numpy as np
from nutil.file import file_load
from nutil.random import h256
from nutil.vars import AutoIntEnum
from data import VERSION, DEV_BUILD
from data.settings import Settings
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
    for ability in abilities:
        ability._setup()
    logger.info(f'Loaded {len(abilities)} abilities.')
    return abilities

ABILITIES = _load_abilities()


# Units
def _load_unit_types():
    all_raw_data = RDF(RDF.CONFIG_DIR / 'units.rdf')
    units = {}
    for unit_name, raw_data in all_raw_data.items():
        iname = internal_name(unit_name)
        if iname in units:
            raise CorruptedDataError(f'Unit name duplication: {iname}')
        raw_data.default['name'] = unit_name
        units[iname] = raw_data
    logger.info(f'Loaded {len(units)} units.')
    return units


RAW_UNITS = _load_unit_types()


metagame_data = str(VERSION) + str(DEV_BUILD) + ''.join(file_load(RDF.CONFIG_DIR / f'{_}.rdf') for _ in (
    'abilities', 'items', 'units',
    Settings.get_setting("source_map"),
    Settings.get_setting("source_spawns"),
))
METAGAME_BALANCE = h256(metagame_data)
METAGAME_BALANCE_SHORT = METAGAME_BALANCE[:4]
logger.info(f'Metagame Balance: {METAGAME_BALANCE_SHORT} ({METAGAME_BALANCE})')
