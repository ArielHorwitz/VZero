import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from pathlib import Path
from data import ROOT_DIR, resource_name
from data.settings import Settings
from nutil.kex import widgets

ASSETS_DIR = ROOT_DIR / 'assets'

FALLBACK_SPRITE = ASSETS_DIR / 'fallback.png'
GRAPHICS_DIR = ASSETS_DIR / 'graphics'
GRAPHICS_UI_DIR = GRAPHICS_DIR / 'ui'
GRAPHICS_ABILITIES_DIR = GRAPHICS_DIR / 'abilities'
GRAPHICS_UNIT_DIR = GRAPHICS_DIR / 'units'

AUDIO_DIR = ASSETS_DIR / 'audio'
SFX_THEME_DIR = AUDIO_DIR / 'theme'
SFX_UI_DIR = AUDIO_DIR / 'ui'
SFX_ABILITY_DIR = AUDIO_DIR / 'ability'


class LoadAssets:
    @classmethod
    def _load_audio_dir(cls, dir, volume=1, prefix=''):
        assert isinstance(dir, Path)
        files = {}
        for file in dir.iterdir():
            if Path.is_dir(file):
                files | cls._load_audio_dir(file, volume, prefix=f'{file.name}_')
            else:
                sound_name = prefix+file.name.split('.')[0]
                files[sound_name] = widgets.Sound.load(file, volume)
                logger.info(f'Loaded sfx {sound_name} from {file}')
        return files

    @classmethod
    def _load_image_dir(cls, dir, prefix=''):
        assert isinstance(dir, Path)
        files = {}
        for file in dir.iterdir():
            if Path.is_dir(file):
                files | cls._load_images_dir(file, prefix=f'{file.name}_')
            else:
                image_name = prefix+file.name.split('.')[0]
                files[image_name] = file
        return files


class Assets:
    missing_sfx = set()
    missing_images = set()
    FALLBACK_SPRITE = FALLBACK_SPRITE

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
                logger.warning(m)
                return None
            logger.critical(m)
            raise KeyError(m)

    @classmethod
    def play_sfx(cls, category, sound_name, allow_exception=False, volume=None, **kwargs):
        sound_name = resource_name(sound_name)
        s = cls.get_sfx(category, sound_name, allow_exception)
        if s is None:
            return
        if volume is None:
            volume = Settings.get_volume(category)
        elif isinstance(volume, str):
            volume = Settings.get_volume(volume)
        logger.debug(f'Playing sfx {sound_name} from category {category}')
        s.play(volume=volume, **kwargs)

    @classmethod
    def get_sprite(cls, category, sprite_name):
        return str(cls.get_image_path(category, resource_name(sprite_name)))

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
                    logger.warning(f'Cannot find category {category} or image name {image_name}. Using fallback: {FALLBACK_SPRITE}')
                return FALLBACK_SPRITE

    SFX = {
        'theme': LoadAssets._load_audio_dir(SFX_THEME_DIR),
        'ui': LoadAssets._load_audio_dir(SFX_UI_DIR),
        'ability': LoadAssets._load_audio_dir(SFX_ABILITY_DIR),
    }
    SPRITES = {
        'ui': LoadAssets._load_image_dir(GRAPHICS_UI_DIR),
        'ability': LoadAssets._load_image_dir(GRAPHICS_ABILITIES_DIR),
        'unit': LoadAssets._load_image_dir(GRAPHICS_UNIT_DIR),
    }
