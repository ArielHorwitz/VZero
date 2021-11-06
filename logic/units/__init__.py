
import pkgutil, copy
from pathlib import Path
from collections import defaultdict
from nutil.display import nprint, adis
from nutil.file import file_load
from logic.mechanics.common import *
from data.load import load_units, load_spawn_weights


class Units:
    ALL_UNITS = None
    SPAWN_WEIGHTS = load_spawn_weights()

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
        units = load_units(unit_types)
        for internal_name in units:
            translated_stats = defaultdict(lambda: {})
            for stat_name, unit_stats in units[internal_name]['stats'].items():
                for value_name, value in unit_stats.items():
                    stat_ = getattr(STAT, stat_name.upper())
                    value_ = getattr(VALUE, value_name.upper())
                    translated_stats[stat_][value_] = float(value)
            units[internal_name]['stats'] = translated_stats
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
            if 'UNIT_TYPES' not in module.__dict__:
                continue
            for unit_name, unit_cls in module.UNIT_TYPES.items():
                if unit_name in unit_types:
                    raise ValueError(f'Unit name duplicate: {unit_name} \
                                     ({unit_types[unit_name]} and {unit_cls})')
                print(f'Found unit type: {unit_name:<30} {unit_cls}')
                unit_types[unit_name] = unit_cls
        return unit_types



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
