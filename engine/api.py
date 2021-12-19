import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import defaultdict
import math
import numpy as np
from nutil.time import humanize_ms
from gui.api import SpriteLabel, SpriteTitleLabel, ProgressBar
from data.load import RDF
from data.settings import Settings
from data.assets import Assets
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

    def draft_label(self):
        return f'{self.__class__}.draft_label() not implemented'

    def draft_details(self):
        return SpriteTitleLabel(None, 'draft_details', '', (0, 0, 0, 0))

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
    gui_flags = defaultdict(lambda: False, {
        'menu': False,
        'menu_dismiss': False,
        'browse': False,
        'browse_toggle': False,
        'browse_dismiss': False,
    })

    def raise_gui_flag(self, flag):
        self.gui_flags[flag] = True

    def check_flag(self, flag):
        r = self.gui_flags[flag]
        self.gui_flags[flag] = False
        return r

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
        self.gui_flags['menu'] = not self.engine.auto_tick
        self.gui_flags['menu_dismiss'] = self.engine.auto_tick

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
        if dist < max(50, hb) and self.sprite_visible_mask(view_size)[uid]:
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

    def select_unit(self, uid):
        self.selected_unit = uid

    # GUI attributes
    hotkeys = {
        'hotkey': ('^ a', lambda: logger.warning(f'{self.__class__}.hotkeys not implemented.')),
    }

    general_label_color = (1,1,1,1)

    @property
    def general_label_text(self):
        return self.time_str

    # Sprites and vfx
    map_size = np.full(2, 5_000)
    map_image_source = Assets.FALLBACK_SPRITE
    request_redraw = 0

    def sprite_visible_mask(self, view_size):
        max_los = self.player_los
        if self.dev_mode:
            max_los = max(max_los, np.linalg.norm(np.array(view_size) / 2))
        return self.engine.unit_distance(0) <= max_los

    def sprite_positions(self):
        return self.engine.get_position()

    def sprite_bars(self):
        max_hps = self.engine.get_stats(slice(None), STAT.HP, value_name=VALUE.MAX)
        hps = self.engine.get_stats(slice(None), STAT.HP) / max_hps
        return hps, np.full(hps.shape, .5)

    def sprite_sizes(self):
        return self.engine.get_stats(slice(None), STAT.HITBOX)

    def sprite_statuses(self, uid):
        return [str(Assets.FALLBACK_SPRITE) for _ in range(uid%3)]

    def get_visual_effects(self):
        return self.engine.get_visual_effects()

    # Menu
    menu_text = ''

    # HUD
    def hud_click(self, hud, index, button):
        logger.warning(f'{self.__class__}.hud_click() not implemented. hud: {hud} index: {index} button: {button}')
        return SpriteTitleLabel(None, 'Title', f'{self.__class__}.hud_click() not implemented. hud: {hud} index: {index} button: {button}', (0.2, 0, 0, 0.5))

    def hud_statuses(self):
        return [SpriteLabel(None, 'status', (0, 0, 0, 0.5)) for _ in range(3)]

    def hud_portrait(self):
        return self.units[self.selected_unit].sprite

    def hud_name(self):
        return self.units[self.selected_unit].name

    def hud_bars(self):
        return [
            ProgressBar(1, f'api.agent_panel_bar() not implemented.', (1, 0, 1, 1)),
            ProgressBar(0.5, '', (1, 1, 1, 0.25)),
        ]

    def hud_left(self):
        return [SpriteLabel(None, f'{self.__class__}.hud_left() not implemented.', None) for _ in range(6)]

    def hud_middle(self):
        return [SpriteLabel(None, f'{self.__class__}.hud_right() not implemented.', None) for _ in range(6)]

    def hud_right(self):
        return [SpriteLabel(None, f'{self.__class__}.hud_right() not implemented.', None) for _ in range(6)]

    # Browse
    def browse_main(self):
        return SpriteTitleLabel(None, 'Title', f'{self.__class__}.browse_main() not implemented.', (0.2, 0, 0, 0.5))

    def browse_elements(self):
        return [SpriteLabel(
            None, f'#{_} {self.__class__}.browse_elements() not implemented.',
            (0.1*_, 0, 1-0.1*_, 0.5)) for _ in range(7)
        ]

    def browse_click(self, index, button):
        logger.warning(f'{self.__class__}.browse_click() not implemented.')
        Assets.play_sfx('ui', 'target', volume=Settings.get_volume('ui'))

    def debug_panel_labels(self):
        return [f'{self.__class__}.debug_panel_label() not implemented.']
