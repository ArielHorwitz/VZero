import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from pathlib import Path
from data import ROOT_DIR, resource_name
from data.settings import Settings
from nutil.kex import widgets

ASSETS_DIR = ROOT_DIR / 'assets'
GRAPHICS_DIR = ASSETS_DIR / 'graphics'
AUDIO_DIR = ASSETS_DIR / 'audio'


class Assets:
    missing_sfx = set()
    missing_images = set()
    FALLBACK_SPRITE = str(ASSETS_DIR / 'fallback.png')
    BLANK_SPRITE = str(ASSETS_DIR / 'blank.png')
    SPRITE_CACHE = {}
    SFX_CACHE = {}

    @classmethod
    def get_sfx(cls, sound_name):
        if sound_name in cls.missing_sfx or sound_name is None:
            return None
        if sound_name in cls.SFX_CACHE:
            return cls.SFX_CACHE[sound_name]

        sound_path_list = sound_name.split('.')
        sound_path = AUDIO_DIR
        while len(sound_path_list) > 0:
            pathpart = resource_name(sound_path_list.pop(0))
            if len(sound_path_list) == 0:
                pathpart = '.'.join((pathpart, 'wav'))
            sound_path = sound_path / pathpart

        if not Path.is_file(sound_path):
            logger.info(f'Failed to find sfx: {sound_name} ({sound_path})')
            cls.missing_sfx.add(sound_name)
            return None
        cls.SFX_CACHE[sound_name] = widgets.Sound.load(str(sound_path))
        return cls.SFX_CACHE[sound_name]

    @classmethod
    def play_sfx(cls, sound_name, volume=None, **kwargs):
        sfx = cls.get_sfx(sound_name)
        if sfx is None:
            return
        if volume is None:
            volume = Settings.get_volume()
        elif isinstance(volume, str):
            volume = Settings.get_volume(volume)
        sfx.play(volume=volume, **kwargs)

    @classmethod
    def get_sprite(cls, sprite_name):
        assert isinstance(sprite_name, str) and len(sprite_name) > 0
        if sprite_name in cls.missing_images:
            return cls.FALLBACK_SPRITE
        if sprite_name in cls.SPRITE_CACHE:
            return cls.SPRITE_CACHE[sprite_name]
        sprite_path_list = sprite_name.split('.')
        sprite_path = GRAPHICS_DIR
        while len(sprite_path_list) > 0:
            pathpart = resource_name(sprite_path_list.pop(0))
            if len(sprite_path_list) == 0:
                pathpart = '.'.join((pathpart, 'png'))
            sprite_path = sprite_path / pathpart
        if not Path.is_file(sprite_path):
            logger.info(f'Failed to find sprite: {sprite_name} ({sprite_path})')
            cls.missing_images.add(sprite_name)
            return cls.FALLBACK_SPRITE
        cls.SPRITE_CACHE[sprite_name] = str(sprite_path)
        return str(sprite_path)
