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
ABILITIES_FILE = CONFIG_DIR/'abilities.bal'
UNITS_FILE = CONFIG_DIR/'units.bal'
MAP_FILE = CONFIG_DIR/'map.bal'

FALLBACK_SPRITE = Path.cwd() / 'data' / 'error.png'
GRAPHICS_DIR = Path.cwd() / 'assets' / 'graphics'
GRAPHICS_UI_DIR = GRAPHICS_DIR / 'ui'
GRAPHICS_UNIT_DIR = GRAPHICS_DIR / 'units'
GRAPHICS_ABILITIES_DIR = GRAPHICS_DIR / 'abilities'

AUDIO_DIR = Path.cwd() / 'assets' / 'audio'
SFX_THEME_DIR = AUDIO_DIR / 'theme'
SFX_UI_DIR = AUDIO_DIR / 'ui'
SFX_ABILITY_DIR = AUDIO_DIR / 'ability'


def resource_name(name):
    return name.lower().replace(' ', '-').replace('_', '-')


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
                    if len(lines) == 0:
                        break
                data[category] = cls.read_category(category_lines)
        return data

    @classmethod
    def read_category(cls, lines):
        data = {}
        subcategory_lines = []
        while not lines[0].startswith('-'):
            subcategory_lines.append(lines.pop(0))
            if len(lines) == 0:
                break
        data[0] = cls.read_subcategory(subcategory_lines)

        if len(lines) == 0:
            return data

        while lines[0].startswith('-'):
            subcategory_name = lines.pop(0).split('- ', 1)[1]
            subcategory_lines = []
            while not lines[0].startswith('-'):
                subcategory_lines.append(lines.pop(0))
                if len(lines) == 0:
                    break
            data[subcategory_name] = cls.read_subcategory(subcategory_lines)
            if len(lines) == 0:
                break
        return data

    @classmethod
    def read_subcategory(cls, lines):
        positional_values = []
        keyed_values = {}
        for line in lines:
            if ': ' in line:
                k, v = line.split(': ', 1)
                keyed_values[k] = try_float(v)
            elif line != '':
                positional_values.append(try_float(line))
        keyed_values[0] = positional_values
        return keyed_values


class Settings:
    SETTINGS = LoadBalFile.load_toplevel(SETTINGS_FILE)
    DEFAULT_SETTINGS = {
        'General': {
            0: {
                'mod': '_fallback',
                'default_zoom': 1.7,
            }
        },
        'Audio': {
            0: {
                'volume_master': 1,
                'volume_music': 1,
                'volume_ui': 1,
                'volume_feedback': 1,
                'volume_sfx': 1,
            }
        },
        'Hotkeys': {
            0: {
                'toggle_play': 'escape',
                'toggle_play_dev': 'spacebar',
                'map_view': 'm',
                'right_click': 'q',
                'abilities': 'qwerasdf',
                'enable_hold_mouse': '1',
                'zoom_default': '0',
                'zoom_in': '=',
                'zoom_out': '-',
            }
        },
    }

    @classmethod
    def get_volume(cls, category=None):
        v = 1
        if category is not None:
            v = cls.get_setting(f'volume_{category}', 'Audio')
        v *= cls.get_setting(f'volume_master', 'Audio')
        return v

    @classmethod
    def get_setting(cls, setting, category='General', subcategory=0):
        for database in (cls.SETTINGS, cls.DEFAULT_SETTINGS):
            if category in database:
                if subcategory in database[category]:
                    if setting in database[category][subcategory]:
                        # Warn if default setting is missing
                        if category not in cls.DEFAULT_SETTINGS:
                            logger.error(f'Missing default settings category: {category}')
                        if subcategory not in cls.DEFAULT_SETTINGS[category]:
                            logger.error(f'Missing default settings subcategory: {subcategory}')
                        if setting not in cls.DEFAULT_SETTINGS[category][subcategory]:
                            logger.error(f'Missing default setting: {setting} from category {category} subcategory {subcategory}')
                        # Finally return the setting value
                        return database[category][subcategory][setting]
                    else:
                        m = f'Cannot find setting {setting} from category {category}, subcategory {subcategory}.'
                else:
                    m = f'Cannot find settings subcategory {subcategory} in category {category}.'
            else:
                m = f'Cannot find settings category {category}.'
        logger.critical(m)
        logger.debug(f'Settings:{cls.SETTINGS}')
        logger.debug(f'Default Settings:{cls.DEFAULT_SETTINGS}')
        raise KeyError(m)


print(f'Default settings:')
logger.debug(f'Default settings:')
for category_name, category in Settings.DEFAULT_SETTINGS.items():
    for subcategory_name, subcategory in category.items():
        for setting, default in subcategory.items():
            m = f'{category_name} [{subcategory_name}] - {setting}: {default}'
            print(m)
            logger.debug(m)


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


class Assets:
    missing_sfx = set()
    missing_images = set()

    @classmethod
    def get_sfx(cls, category, sound_name, allow_exception=True):
        sound_name = resource_name(sound_name)
        if sound_name in cls.missing_sfx and not allow_exception:
            return None
        try:
            return cls.SFX[category][sound_name]
        except KeyError:
            cls.missing_sfx.add(sound_name)
            m = f'Failed to find sfx {sound_name} from category {category}'
            if not allow_exception:
                logger.info(m)
                return None
            logger.critical(m)
            raise KeyError(m)

    @classmethod
    def play_sfx(cls, category, sound_name, allow_exception=True, **kwargs):
        sound_name = resource_name(sound_name)
        s = cls.get_sfx(category, sound_name, allow_exception)
        if s is None:
            return
        logger.debug(f'Playing sfx {sound_name} from category {category}')
        s.play(**kwargs)

    @classmethod
    def get_sprite(cls, category, sprite_name):
        return str(cls.get_image_path(category, sprite_name))

    @classmethod
    def get_image_path(cls, category, image_name, allow_exception=False):
        image_name = resource_name(image_name)
        try:
            return cls.SPRITES[category][image_name]
        except KeyError:
            if allow_exception:
                m = f'Cannot find image name: {image_name} or category {category}'
                logger.critical(m)
                raise KeyError(m)
            else:
                if not Path.is_file(FALLBACK_SPRITE):
                    m = f'Cannot find fallback sprite: {FALLBACK_SPRITE}'
                    logger.critical(m)
                    raise RuntimeError(m)
                if image_name not in cls.missing_images:
                    cls.missing_images.add(image_name)
                    logger.warning(f'Cannot find category or image name: {category}, {image_name}. Using fallback: {FALLBACK_SPRITE}')
                return FALLBACK_SPRITE

    SFX = {
        'theme': LoadAssets.load_audio_dir(SFX_THEME_DIR),
        'ui': LoadAssets.load_audio_dir(SFX_UI_DIR),
        'ability': LoadAssets.load_audio_dir(SFX_ABILITY_DIR),
    }
    SPRITES = {
        'unit': LoadAssets.load_image_dir(GRAPHICS_UNIT_DIR),
        'ability': LoadAssets.load_image_dir(GRAPHICS_ABILITIES_DIR),
    }


class LoadMechanics:
    RAW_ABILITY_DATA = LoadBalFile.load_toplevel(ABILITIES_FILE)
    RAW_UNIT_DATA = LoadBalFile.load_toplevel(UNITS_FILE)
    RAW_MAP_DATA = LoadBalFile.load_toplevel(MAP_FILE)
