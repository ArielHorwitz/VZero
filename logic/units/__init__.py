
import pkgutil, copy
from pathlib import Path
from collections import defaultdict
from nutil.display import nprint
from nutil.file import file_load
from logic.mechanics.common import *



class Units:
    ALL_UNITS = None
    SPAWN_WEIGHTS = {
        'ratzan': (4, 7),
        'blood-imp': (4, 4),
        'null-ice': (3, 1),
        'winged-snake': (0, 1),
        'fire-elemental': (2, 1),
        'folphin': (3,1),
        'treasure': (0, 1),
        'heros-treasure': (0,1),
    }

    @classmethod
    def new_unit(cls, unit_type_name, *args, **kwargs):
        if cls.ALL_UNITS is None:
            cls.ALL_UNITS = cls._get_all_units()
        if unit_type_name not in cls.ALL_UNITS:
            raise ValueError(f'Unit type name not found: {unit_type_name}')
        data = cls.ALL_UNITS[unit_type_name]
        unit_cls = data['type']
        kwargs['params'] = copy.deepcopy(data['params'])
        kwargs['internal_name'] = unit_type_name
        kwargs['name'] = copy.copy(data['name'])
        unit = unit_cls(*args, **kwargs)
        return unit

    @classmethod
    def get_starting_stats(cls, unit_type_name):
        if cls.ALL_UNITS is None:
            cls.ALL_UNITS = cls._get_all_units()
        if unit_type_name not in cls.ALL_UNITS:
            raise ValueError(f'Unit type name not found: {unit_type_name}\n{cls.ALL_UNITS}')
        custom_stats = cls.ALL_UNITS[unit_type_name]['stats']
        return cls.combine_starting_stats(custom_stats)

    @classmethod
    def _get_all_units(cls):
        unit_types = cls._get_all_unit_types()
        units = cls._get_units_config(unit_types)
        return units

    @classmethod
    def combine_starting_stats(cls, custom=None, base=None):
        stats = copy.deepcopy(DEFAULT_STARTING_STATS if base is None else base)
        if custom is not None:
            for stat in STAT:
                if stat in custom:
                    for value in VALUE:
                        if value in custom[stat]:
                            stats[stat][value] = custom[stat][value]
        return stats

    @classmethod
    def _get_all_unit_types(cls):
        unit_types = {}
        for loader, modname, ispkg in pkgutil.iter_modules(__path__, __name__+'.'):
            module = __import__(modname, fromlist='UNITS')
            for unit_name, unit_cls in module.UNIT_TYPES.items():
                if unit_name in unit_types:
                    raise ValueError(f'Unit name duplicate: {unit_name} \
                                     ({unit_types[unit_name]} and {unit_cls})')
                print(f'Found unit type: {unit_name:<30} {unit_cls}')
                unit_types[unit_name] = unit_cls
        return unit_types

    @classmethod
    def _get_units_config(cls, unit_types):
        raw = file_load(Path.cwd()/'config'/'units.bal')
        all_units = {}
        line_number = 0
        lines = raw.split('\n')
        while line_number < len(lines):
            if lines[line_number].startswith('='):
                name = lines[line_number].split('= ', 1)[1]
                unit_type = lines[line_number + 1]
                if unit_type not in unit_types:
                    raise ValueError(f'Unrecognized unit type: {unit_type}')
                unit_type = unit_types[unit_type]
                line_number += 2
                unit_data = {
                    'type': unit_type,
                    'name': name,
                    'params': {},
                    'stats': defaultdict(lambda: {}),
                }
                while line_number < len(lines) and not lines[line_number].startswith('-'):
                    if ':' not in lines[line_number]:
                        line_number += 1
                        continue
                    param, value = lines[line_number].split(':')
                    line_number += 1
                    unit_data['params'][param] = value
                while line_number < len(lines) and not lines[line_number].startswith('='):
                    if ':' not in lines[line_number]:
                        line_number += 1
                        continue
                    stat, value = lines[line_number].split(':')
                    line_number += 1
                    if '.' in stat:
                        stat_name, value_name = stat.split('.')
                    else:
                        stat_name = stat
                        value_name = 'current'
                    stat_name = getattr(STAT, stat_name.upper())
                    value_name = getattr(VALUE, value_name.upper())
                    unit_data['stats'][stat_name][value_name] = float(value)
                internal_name = name.lower().replace(' ', '-')
                all_units[internal_name] = unit_data
            else:
                line_number += 1
        return all_units


DEFAULT_STARTING_STATS = {
    STAT.POS_X: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.POS_Y: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.GOLD: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.HP: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: 0,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MOVE_SPEED: {
        VALUE.CURRENT: 1,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MANA: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_00,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.RANGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.DAMAGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.ATTACK_SPEED: {
        VALUE.CURRENT: 100,
        VALUE.MIN_VALUE: 10,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.LIFESTEAL: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
}
