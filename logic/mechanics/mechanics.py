import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import copy
from collections import defaultdict
from data.load import LoadMechanics, Assets, resource_name
from logic.mechanics import import_mod_module
from logic.mechanics.common import *
from logic.mechanics.player import Player
mod_definitions = import_mod_module('definitions')
logger.info(f'Imported mod definitions: {mod_definitions}')


missing_resources = set()


class __Mechanics:
    def __init__(self):
        self.abilities = self.__load_abilities(LoadMechanics.RAW_ABILITY_DATA)
        self.unit_types = self.__load_unit_types(LoadMechanics.RAW_UNIT_DATA)
        self.spawn_weights = self.__load_spawn_weights(LoadMechanics.RAW_MAP_DATA['Spawn weights'][0])

    def cast_ability(self, aid, api, uid, target):
        if uid == 0:
            logger.debug(f'uid {uid} casting ability {aid.name} to {target}')
        ability = self.abilities[aid]
        r = ability.cast(api, uid, target)
        if r is None:
            m = f'Ability {ability.__class__} cast() method returned None. Must return FAIL_RESULT on fail or aid on success.'
            logger.error(m)
            raise ValueError(m)
        if isinstance(r, FAIL_RESULT):
            logger.debug(f'uid {uid} tried casting {aid.name} but failed with {r.name}')
        else:
            if aid not in missing_resources and Assets.get_sfx('ability', ability.name, allow_exception=False) is not None:
                api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': ability.name, 'call_source': (uid, aid, __name__)})
        return r

    def get_new_unit(self, unit_type, api, uid, allegiance):
        internal_name = resource_name(unit_type)
        unit_data = self.unit_types[internal_name]
        name = copy.deepcopy(unit_data['name'])
        params = copy.deepcopy(unit_data['params'])
        unit_cls = unit_data['cls']
        unit = unit_cls(api, uid, name, allegiance, params)
        logger.debug(f'Mechanics created new unit {internal_name} with uid {uid} and params: {params}')
        return unit

    def get_starting_stats(self, unit_type):
        name = resource_name(unit_type)
        stats = self.unit_types[name]['stats']
        return self._combine_starting_stats(stats)

    @property
    def default_starting_stats(self):
        return mod_definitions.DEFAULT_STARTING_STATS

    @property
    def ability_classes(self):
        return mod_definitions.ABILITY_CLASSES

    @property
    def unit_classes(self):
        return {**mod_definitions.UNIT_CLASSES, 'player': Player}

    def __load_abilities(self, raw_data):
        abilities = []
        logger.info('Loading abilities:')
        raw_items = tuple(raw_data.items())
        for aid in ABILITY:
            ability_name, ability_data = raw_items[aid]
            logger.info(f'{aid} {ability_name} {ability_data}')
            ability_type = ability_data[0][0][0]
            stats = {}
            if 'stats' in ability_data:
                stats = ability_data['stats']
                del stats[0]
            ability_instance = self.ability_classes[ability_type](
                aid, ability_name, stats)
            assert len(abilities) == aid
            abilities.append(ability_instance)
        return abilities

    def __load_spawn_weights(self, raw_data):
        logger.info(f'Loading map spawn weights:')
        spawn_weights = {}
        for unit_name, spawn_data in raw_data.items():
            if unit_name == 0:
                continue
            internal_name = resource_name(unit_name)
            a, b = spawn_data.split(', ')
            logger.info(f'{internal_name} *{a}, cluster size: {b}')
            spawn_weights[internal_name] = float(a), int(b)
        return spawn_weights

    def __load_unit_types(self, raw_data):
        logger.info('Loading unit types:')
        units = {}
        for unit_name, unit_data in copy.deepcopy(raw_data).items():
            internal_name = resource_name(unit_name)
            if internal_name in units:
                m = f'Unit name duplication: {internal_name}'
                logger.critical(m)
                raise ValueError(m)
            unit_type = unit_data[0][0][0]
            unit_cls = self.unit_classes[unit_type]
            raw_stats = unit_data['stats']
            params = unit_data[0]
            del params[0]
            stats = self.__translate_stats(raw_stats)
            logger.info(f'{unit_name} ({unit_type} - {unit_cls})')
            units[internal_name] = {
                'name': unit_name,
                'cls': unit_cls,
                'stats': stats,
                'params': params,
            }
        return units

    def _combine_starting_stats(self, custom=None, base=None):
        stats = copy.deepcopy(self.default_starting_stats if base is None else base)
        if custom is not None:
            for stat in STAT:
                if stat in custom:
                    for value in VALUE:
                        if value in custom[stat]:
                            stats[stat][value] = custom[stat][value]
        return stats

    @staticmethod
    def __translate_stats(raw_stats):
        translated_stats = defaultdict(lambda: {})
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
            translated_stats[stat_][value_] = float(raw_value)
        return dict(translated_stats)


Mechanics = __Mechanics()
