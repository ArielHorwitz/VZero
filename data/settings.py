import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data.load import RDF


class Settings:
    SETTINGS = RDF.load(RDF.CONFIG_DIR / 'settings.cfg')
    DEFAULT_SETTINGS = {
        'General': {
            0: {
                'dev_build': 0,
                'dev_items': 0,
                'start_maximized': 1,
                'window_resolution': '1024, 768',
                'default_zoom': 0.5,
                'map_zoom': 0.4,
            }
        },
        'Audio': {
            0: {
                'volume_master': 0.3,
                'volume_sfx': 1,
                'volume_ui': 0.5,
                'volume_feedback': 0.5,
            }
        },
        'Hotkeys': {
            0: {
                'start_encounter': 'spacebar',
                'toggle_play': 'spacebar',
                'control0': 'escape',
                'control1': 'f1',
                'control2': 'f2',
                'control3': 'f3',
                'control4': 'f4',
                'map_view': 'tab',
                'open_menu1': 'f5',
                'open_menu2': 'f6',
                'right_click': 'q',
                'abilities': 'qwerasdf',
                'items': '1234zxcv',
                'enable_hold_mouse': 1,
                'zoom_default': '0',
                'zoom_in': '=',
                'zoom_out': '-',
                'dev1': '^+ f9',
                'dev2': '^+ f10',
                'dev3': '^+ f11',
                'dev4': '^+ f12',
            },
        },
        'Personal': {
            0: {
                'preset_loadout1': 'null',
                'preset_loadout2': 'null',
                'preset_loadout3': 'null',
                'preset_loadout4': 'null',
            },
        }
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


logger.info(f'Found settings:')
for category_name, category in Settings.DEFAULT_SETTINGS.items():
    for subcategory_name, subcategory in category.items():
        for setting in subcategory.keys():
            value = Settings.get_setting(setting, category=category_name, subcategory=subcategory_name)
            m = f'Default {category_name} [{subcategory_name}] - {setting}: {value}'
            logger.info(m)
