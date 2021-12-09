import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from nutil.time import humanize_ms
from gui.api import SpriteLabel, SpriteTitleLabel, ProgressBar
from data.load import RDF
from data.settings import Settings
from data.assets import Assets, FALLBACK_SPRITE
from engine.encounter import Encounter as EncounterEngine
from engine.common import *


ABILITY_HOTKEYS = Settings.get_setting('abilities', 'Hotkeys')
RIGHT_CLICK_ABILITY = Settings.get_setting('right_click', 'Hotkeys')


class GameAPI:
    encounter_api = None
    button_names = []

    def __init__(self):
        logger.warning(f'{self.__class__}.__init__() not implemented.')

    # GUI handlers
    def new_encounter(self):
        logger.warning(f'{self.__class__}.new_encounter() not implemented.')

    def draft_click(self, index, button):
        logger.warning(f'{self.__class__}.draft_click() not implemented for {index} {button}.')

    def loadout_click(self, index, button):
        logger.warning(f'{self.__class__}.loadout_click() not implemented for {index} {button}.')

    # GUI properties
    def button_click(self, index):
        logger.warning(f'{self.__class__}.button_click() not implemented for {index}.')

    def draft_info_box(self):
        return SpriteLabel(None, 'draft_info_box', (0, 0, 0, 0))

    def draft_info_label(self):
        return f'{self.__class__}.draft_info_label()\nnot implemented.'

    def draft_boxes(self):
        return [
            SpriteLabel(None, f'Draft #{i}', (0.5, 0.5, 0.5, 1)) for i in range(20)
        ]

    def loadout_boxes(self):
        return [
            SpriteLabel(None, f'Loadout #{i}', (0.25, 0.5, 0.5, 1)) for i in range(8)
        ]


class EncounterAPI:
    dev_mode = True
    show_debug = True
    selected_unit = 0
    player_los = 2000
    overlay_text = ''
    control_buttons = ['Menu']

    def __init__(self):
        self.engine = EncounterEngine(self)
        logger.warning(f'{self.__class__}.__init__() not implemented (will not spawn anything).')

    # Engine attributes
    @property
    def units(self):
        return self.engine.units

    @property
    def time_str(self):
        return humanize_ms(self.engine.ticktime * self.engine.tick)

    @property
    def view_center(self):
        return self.engine.get_position(0)

    @property
    def target_crosshair(self):
        return self.engine.get_position(0, value_name=VALUE.TARGET)

    # Logic handlers
    def update(self):
        self.engine.update()

    def hp_zero(self, uid):
        logger.warning(f'{self.__class__}.hp_zero() not implemented.')

    def status_zero(self, uid, status):
        logger.warning(f'{self.__class__}.status_zero() not implemented.')

    # User input
    def control_button_click(self, index):
        if index == 0:
            self.toggle_play()

    def toggle_play(self, set_to=None, play_sfx=True):
        set_to = set_to if set_to is not None else not self.engine.auto_tick
        changed = set_to != self.engine.auto_tick
        self.engine.set_auto_tick(set_to)
        logger.debug(f'Logic toggled play')
        if play_sfx and changed:
            if self.engine.auto_tick is True:
                Assets.play_sfx('ui', 'play', volume=Settings.get_volume('ui'))
            else:
                Assets.play_sfx('ui', 'pause', volume=Settings.get_volume('ui'))

    def user_click(self, target, button, view_size):
        if button == 'right':
            aindex = ABILITY_HOTKEYS.index(RIGHT_CLICK_ABILITY)
            self.quickcast(aindex, target)
        elif button == 'left':
            self.user_select(target, view_size)
        else:
            logger.warning(f'{self.__class__}.user_click() with button: {button} not implemented.')

    def user_select(self, target, view_size):
        uid, dist = self.engine.nearest_uid(target, alive_only=False)
        hb = self.engine.get_stats(uid, STAT.HITBOX)
        if dist < max(50, hb) and self.get_visible_uids(view_size)[uid]:
            self.select_unit(uid)
            Assets.play_sfx('ui', 'select',
                volume=Settings.get_volume('feedback'))
        else:
            self.select_unit(0)
            uid, hb = 0, self.engine.get_stats(0, STAT.HITBOX)
        self.engine.add_visual_effect(VisualEffect.SPRITE, 60, {
            'uid': uid,
            'fade': 100,
            'category': 'ui',
            'source': 'crosshair2',
            'size': (hb*2.1, hb*2.1),
            'tint': (0, 0, 0),
        })

    def quickcast(self, ability_index, target):
        logger.warning(f'{self.__class__}.quickcast() not implemented.')

    def itemcast(self, item_index, target):
        logger.warning(f'{self.__class__}.itemcast() not implemented.')

    def itemsell(self, item_index, target):
        logger.warning(f'{self.__class__}.itemsell() not implemented.')

    def ability_sort(self, ability_index, target):
        logger.warning(f'{self.__class__}.ability_sort() not implemented.')

    def item_sort(self, item_index, target):
        logger.warning(f'{self.__class__}.item_sort() not implemented.')

    def user_hotkey(self, hotkey, target):
        logger.warning(f'{self.__class__}.user_hotkey() not implemented.')
        if hotkey == 'toggle_play':
            self.toggle_play()
        elif 'control' in hotkey:
            self.show_modal = not self.show_modal

    def select_unit(self, uid):
        self.selected_unit = uid

    # GUI attributes
    hotkeys = {
        'hotkey': ('^ a', lambda: logger.warning(f'{self.__class__}.hotkeys not implemented.')),
    }

    @property
    def general_label_text(self):
        return self.time_str

    # Units and vfx
    map_size = np.full(2, 5_000)
    map_image_source = FALLBACK_SPRITE
    request_redraw = 0

    def get_visible_uids(self, view_size):
        max_los = self.player_los
        if self.dev_mode:
            max_los = max(max_los, np.linalg.norm(np.array(view_size) / 2))
        return self.engine.unit_distance(0) <= max_los

    def get_all_positions(self):
        return self.engine.get_position()

    def get_sprite_bars(self):
        max_hps = self.engine.get_stats(slice(None), STAT.HP, value_name=VALUE.MAX)
        hps = self.engine.get_stats(slice(None), STAT.HP) / max_hps
        return hps, max_hps

    def get_sprite_size(self, uid=None):
        if uid is None:
            uid = slice(None)
        return self.engine.get_stats(uid, STAT.HITBOX)

    def get_visual_effects(self):
        return self.engine.get_visual_effects()

    # Menu
    menu_text = ''

    @property
    def show_menu(self):
        return not self.engine.auto_tick and not self.dev_mode

    # Unit panel
    def agent_panel_sprite(self):
        return self.units[self.selected_unit].sprite

    def agent_panel_bars(self):
        return [
            ProgressBar(1, f'api.agent_panel_bar() not implemented.', (1, 0, 1, 1)),
            ProgressBar(0.5, '', (1, 1, 1, 0.25)),
        ]

    def agent_panel_boxes(self):
        return [SpriteLabel(None, f'{self.__class__}.agent_panel_boxes_labels() not implemented.', None) for _ in range(6)]

    def agent_panel_label(self):
        return f'{self.__class__}.agent_panel_label() not implemented.'

    def debug_panel_labels(self):
        return [f'{self.__class__}.debug_panel_label() not implemented.']

    # HUD
    def hud_sprite_labels(self):
        return [SpriteLabel(None, 'HUD not\nimplemented', (0, 0, 0, 0.5)) for _ in range(8)]

    def hud_aux_sprite_labels(self):
        return [SpriteLabel(None, 'HUD Aux not implemented', (0, 0, 0, 0.5)) for _ in range(8)]

    # Modal
    show_modal_grid = False
    show_modal_browse = False

    def modal_browse_main(self):
        return SpriteTitleLabel(None, 'Title', f'{self.__class__}.modal_browse_main() not implemented.', (0.2, 0, 0, 0.5))

    def modal_browse_sts(self):
        return [SpriteLabel(
            None, f'#{_} {self.__class__}.modal_browse_sts() not implemented.',
            (0.1*_, 0, 1-0.1*_, 0.5)) for _ in range(7)
        ]

    def modal_grid(self):
        return [SpriteTitleLabel(
            None, 'Title',
            f'#{_} {self.__class__}.modal_grid() not implemented.',
            (0.1*_, 0, 1-0.1*_, 0.5)) for _ in range(7)
        ]

    def modal_click(self, index, button):
        logger.warning(f'{self.__class__}.modal_click() not implemented.')
        Assets.play_sfx('ui', 'target', volume=Settings.get_volume('ui'))
