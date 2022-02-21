import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from nutil.file import file_dump
from data.load import RDF


_DEFAULT_SETTINGS_STR = """
=== General
default_window: fullscreen
full_resolution: 1920, 1080
window_resolution: 1024, 768
default_zoom: 40
enable_hold_mouse: 1
enable_hold_key: 0
source_map: map
source_spawns: spawns
dev_build: 0
auto_log: 1
log_interval: 3000

=== UI
detailed_mode: 1
auto_dismiss_tooltip: 100
auto_tooltip: 0
hud_scale: 1
decorations: 0.75
feedback_sfx_cooldown: 350
fog: 45
fog_color: 0, 0, 0, 0.6

=== Audio
volume_master: 0.15
volume_sfx: 1
volume_ui: 0.5
volume_feedback: 0.5
volume_monster_death: 0.4

=== Hotkeys
toggle_fullscreen: f11
toggle_borderless: ! f11
toggle_menu: escape
toggle_play: spacebar
toggle_shop: f1
toggle_map: tab
toggle_detailed: ! alt

loot: z
alt_modifier: +
ability1: q
ability2: w
ability3: e
ability4: r
ability5: a
ability6: s
ability7: d
ability8: f
item1: 1
item2: 2
item3: 3
item4: 4
item5: 5
item6: 6
item7: 7
item8: 8

reset_view: home
unpan: end
zoom_in: =
zoom_out: -
pan_up: up
pan_down: down
pan_left: left
pan_right: right

refresh: f5

dev1: ^+ f9
dev2: ^+ f10
dev3: ^+ f11
dev4: ^+ f12

=== Loadouts

"""
file_dump(RDF.CONFIG_DIR / 'settings-auto-generated-defaults.cfg', _DEFAULT_SETTINGS_STR)


class Settings:
    DEFAULT_SETTINGS = RDF(_DEFAULT_SETTINGS_STR, raw_str=True)
    USER_SETTINGS = RDF(RDF.CONFIG_DIR / 'settings.cfg')

    @classmethod
    def reload_settings(cls):
        cls.USER_SETTINGS = RDF(RDF.CONFIG_DIR / 'settings.cfg')
        logger.info(f'Reloaded user-defined settings: {Settings.USER_SETTINGS}')

    @classmethod
    def get_volume(cls, category=None):
        v = 1
        if category is not None:
            v = cls.get_setting(f'volume_{category}', 'Audio')
        v *= cls.get_setting(f'volume_master', 'Audio')
        return v

    @classmethod
    def get_setting(cls, setting, category='General'):
        try:
            return cls.USER_SETTINGS[category].default[setting]
        except Exception as e:
            return cls.DEFAULT_SETTINGS[category].default[setting]


logger.info(f'Found default settings: {Settings.DEFAULT_SETTINGS}')
logger.info(f'Found user-defined settings: {Settings.USER_SETTINGS}')
