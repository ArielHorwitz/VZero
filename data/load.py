
from pathlib import Path
from collections import defaultdict
from nutil.file import file_load


CONFIG_DIR = Path.cwd()/'config'


def load_abilities():
    raw = file_load(CONFIG_DIR/'abilities.bal')
    all_abilities = {}
    line_number = 0
    lines = raw.split('\n')
    while line_number < len(lines):
        if lines[line_number].startswith('='):
            name = lines[line_number].split('= ', 1)[1]
            ability_type = lines[line_number + 1]
            line_number += 1
            ability_data = {
                'name': name,
                'type': ability_type,
                'params': {},
            }
            while line_number < len(lines) and not lines[line_number].startswith('='):
                if ':' not in lines[line_number]:
                    line_number += 1
                    continue
                param, value = lines[line_number].split(':')
                ability_data['params'][param] = float(value)
                line_number += 1
            internal_name = name.upper().replace(' ', '_')
            all_abilities[internal_name] = ability_data
        else:
            line_number += 1
    return all_abilities


def load_spawn_weights():
    raw = file_load(CONFIG_DIR/'map.bal')
    lines = raw.split('\n')
    spawn_weights = {}
    line_number = 0
    while line_number < len(lines):
        if ':' not in lines[line_number]:
            line_number += 1
            continue
        unit_name, value = lines[line_number].split(':')
        line_number += 1
        unit_name = unit_name.lower().replace(' ', '-')
        cluster_count, cluster_size = value.split(',')
        spawn_weights[unit_name] = (float(cluster_count), int(cluster_size))
    return spawn_weights


def load_settings():
    raw = file_load(CONFIG_DIR/'settings.cfg')
    lines = raw.split('\n')
    settings = {}
    for line in lines:
        if ':' not in line:
            continue
        k, v = line.split(':')
        settings[k] = v
    return settings


def load_units(unit_types):
    raw = file_load(CONFIG_DIR/'units.bal')
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
                unit_data['stats'][stat_name][value_name] = value
            internal_name = name.lower().replace(' ', '-')
            all_units[internal_name] = unit_data
        else:
            line_number += 1
    return all_units
