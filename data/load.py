import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from pathlib import Path
from collections import defaultdict
from nutil.vars import try_float
from nutil.file import file_load
from nutil.kex import widgets

CONFIG_DIR = Path.cwd() / 'config'
SETTINGS_FILE = CONFIG_DIR/'settings.cfg'

FALLBACK_SPRITE = Path.cwd() / 'data' / 'error.png'
GRAPHICS_DIR = Path.cwd() / 'assets' / 'graphics'
GRAPHICS_UI_DIR = GRAPHICS_DIR / 'ui'
GRAPHICS_UNIT_DIR = GRAPHICS_DIR / 'units'
GRAPHICS_ABILITIES_DIR = GRAPHICS_DIR / 'abilities'

AUDIO_DIR = Path.cwd() / 'assets' / 'audio'
SFX_THEME_DIR = AUDIO_DIR / 'theme'
SFX_UI_DIR = AUDIO_DIR / 'ui'
SFX_ABILITY_DIR = AUDIO_DIR / 'ability'


DEFAULT_SETTINGS = {
    'volume': 1,
    'zoom': 1.7,
}


class LoadBalFile:
    @classmethod
    def load_toplevel(cls, file):
        return cls.read_toplevel(cls.load(file))

    @classmethod
    def load_category(cls, file):
        return cls.read_category(cls.load(file))

    @classmethod
    def load_subcategory(cls, file):
        return cls.read_subcategory(cls.load(file))

    @classmethod
    def load(cls, file):
        raw = file_load(file)
        lines = raw.split('\n')
        return lines

    @classmethod
    def read_toplevel(cls, lines):
        data = {}
        while len(lines) > 0:
            line = lines.pop(0)
            if line.startswith('='):
                category = line.split('= ', 1)[1]
                category_lines = []
                while not lines[0].startswith('='):
                    category_lines.append(lines.pop(0))
                data[category] = cls.read_category(category_lines)

    @classmethod
    def read_category(cls, lines):
        data = {}
        line = lines.pop(0)
        while not line.startswith('-'):
            subcategory_lines = []
            while not lines[0].startswith('-'):
                subcategory_lines.append(lines.pop(0))
            data[0] = cls.read_subcategory(subcategory_lines)

        while not line.startswith('-'):
            subcategory_name = line.split('- ', 1)[1]
            subcategory_lines = []
            while not lines[0].startswith('-'):
                sub_category_lines.append(lines.pop(0))
            data[subcategory_name] = cls.read_subcategory(subcategory_lines)
        return data

    @classmethod
    def read_subcategory(cls, lines):
        positional_values = []
        keyed_values = {}
        for line in lines:
            if ':' in line:
                k, v = line.split(': ', 1)
                keyed_values[k] = try_float(v)
            else:
                positional_values.append(try_float(line))
        keyed_values[0] = positional_values
        return keyed_values


class LoadAssets:
    @classmethod
    def load_audio_dir(cls, dir, volume=1, prefix=''):
        assert isinstance(dir, Path)
        files = {}
        for file in dir.iterdir():
            if Path.is_dir(file):
                files | cls.load_audio_dir(file, volume,
                                           prefix=f'{file.name}_')
            else:
                sound_name = prefix+file.name.split('.')[0]
                files[sound_name] = widgets.Sound.load(file, volume)
                logger.info(f'Loaded sfx {sound_name} from {file}')
        return files

    @classmethod
    def get_image_path(cls, category, image_name, allow_exception=False):
        try:
            return cls.SPRITES[category][image_name]
        except KeyError:
            if allow_exception:
                m = f'Cannot find category or image name: {category}, {image_name}'
                logger.critical(m)
                raise KeyError(m)
            else:
                if not Path.is_file(FALLBACK_SPRITE):
                    m = f'Cannot find fallback sprite: {FALLBACK_SPRITE}'
                    logger.critical(m)
                    raise RuntimeError(m)
                return FALLBACK_SPRITE

    @classmethod
    def load_image_dir(cls, dir, prefix=''):
        assert isinstance(dir, Path)
        files = {}
        for file in dir.iterdir():
            if Path.is_dir(file):
                files | cls.load_images_dir(file, prefix=f'{file.name}_')
            else:
                image_name = prefix+file.name.split('.')[0]
                files[image_name] = file
        return files


class Settings:
    SETTINGS = LoadBalFile.load_subcategory(SETTINGS_FILE)

    @classmethod
    def get_setting(cls, setting):
        if setting in cls.SETTINGS:
            return cls.SETTINGS[setting]
        elif setting in DEFAULT_SETTINGS:
            return DEFAULT_SETTINGS[setting]
        else:
            m = f'Cannot find setting from file or defaults: {setting}'
            logger.critical(m)
            raise KeyError(m)


class Assets:
    @classmethod
    def get_sfx(cls, category, sound_name, allow_exception=True):
        if not allow_exception:
            if category not in cls.SFX:
                return None
            if sound_name not in cls.SFX[category]:
                return None
        return cls.SFX[category][sound_name]
        try:
            return cls.SFX[category][sound_name]
        except KeyError:
            m = f'Failed to find category sfx: \'{sound_name}\' from category \'{category}\''
            logger.critical(m)
            raise KeyError(m)

    @classmethod
    def play_sfx(cls, category, sound_name, volume=1, allow_exception=True):
        logger.debug(f'Looking up sfx \'{sound_name}\' from category \'{category}\'')
        s = cls.get_sfx(category, sound_name, allow_exception)
        if s is None:
            logger.info(f'Didnt find and skiping playing sfx \'{sound_name}\' from category \'{category}\'')
            return
        logger.debug(f'Playing sfx \'{sound_name}\' from category \'{category}\'')
        s.play(volume=volume)

    @classmethod
    def get_sprite(cls, category, sprite_name):
        return str(cls.SPRITES[category][sprite_name])

    SFX = {
        'theme': LoadAssets.load_audio_dir(SFX_THEME_DIR),
        'ui': LoadAssets.load_audio_dir(SFX_UI_DIR),
        'ability': LoadAssets.load_audio_dir(SFX_ABILITY_DIR),
    }
    SPRITES = {
        'unit': LoadAssets.load_image_dir(GRAPHICS_UNIT_DIR),
        'ability': LoadAssets.load_image_dir(GRAPHICS_ABILITIES_DIR),
    }


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
