import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import defaultdict
import math
import numpy as np
from nutil.vars import minmax, nsign, NP
from nutil.time import humanize_ms
from gui.api import SpriteBox, SpriteTitleLabel, ProgressBar
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
    title_text = '« Drafting Phase »'

    def __init__(self):
        logger.warning(f'{self.__class__}.__init__() not implemented.')

    # GUI handlers
    def new_encounter(self):
        logger.warning(f'{self.__class__}.new_encounter() not implemented.')

    def leave_encounter(self):
        logger.warning(f'{self.__class__}.leave_encounter() not implemented.')

    def draft_click(self, index, button):
        logger.warning(f'{self.__class__}.draft_click() not implemented for {index} {button}.')

    def loadout_click(self, index, button):
        logger.warning(f'{self.__class__}.loadout_click() not implemented for {index} {button}.')

    def loadout_drag_drop(self, origin, target, button):
        logger.warning(f'{self.__class__}.loadout_drag_drop() not implemented for {button} ({origin} -> {target}).')

    # GUI properties
    def button_click(self, index):
        logger.warning(f'{self.__class__}.button_click() not implemented for {index}.')

    def draft_label(self):
        return f'{self.__class__}.draft_label() not implemented'

    def draft_details(self):
        return SpriteTitleLabel(None, 'draft_details', '', (0, 0, 0, 0))

    def draft_boxes(self):
        return [
            SpriteBox(None, f'Draft #{i}', (0.5, 0.5, 0.5, 1), None) for i in range(20)
        ]

    def loadout_boxes(self):
        return [
            SpriteBox(None, f'Loadout #{i}', (0.25, 0.5, 0.5, 1), None) for i in range(8)
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
    gui_size = np.array([1024,768])
    upp = default_upp = 2
    view_offset = None
    show_hud = True
    map_mode = False
    map_size = np.array([10_000, 10_000])

    def raise_gui_flag(self, flag):
        self.gui_flags[flag] = True

    def check_flag(self, flag):
        r = self.gui_flags[flag]
        self.gui_flags[flag] = False
        return r

    def __init__(self):
        self.engine = EncounterEngine(self)
        logger.warning(f'{self.__class__}.__init__() not implemented (will not spawn anything).')

    # Display settings
    @property
    def view_center(self):
        if self.map_mode:
            return self.map_size / 2
        return self.engine.get_position(0) if self.view_offset is None else self.view_offset

    @property
    def upp(self):
        if self.map_mode:
            return self.fit_upp(self.map_size * 1.1)
        return self.default_upp

    def zoom_in(self):
        if not self.map_mode:
            self.set_zoom(d=1.15)

    def zoom_out(self):
        if not self.map_mode:
            self.set_zoom(d=-1.15)

    def set_zoom(self, d=None, v=None):
        if v is not None:
            self.default_upp = v
            return
        if d is None:
            self.default_upp = 1 / (Settings.get_setting('default_zoom')/100)
        else:
            self.default_upp *= abs(d)**(-1*nsign(d))
        self.default_upp = minmax(
            self.fit_upp(self.engine.get_stats(0, STAT.HITBOX)),
            self.fit_upp(self.map_size * 0.5),
            self.default_upp
        )
        logger.info(f'Set upp: {self.default_upp}')

    def fit_upp(self, real_size):
        return max(np.array(real_size) / self.gui_size)

    def pan(self, d, a=None):
        if a is None:
            a = min(self.view_size) * 0.15
        if self.view_offset is None:
            self.view_offset = self.view_center
        hoff = (d=='right') - (d=='left')
        voff = (d=='up') - (d=='down')
        offset = np.array([a*hoff, a*voff])
        self.view_offset += offset

    # Engine attributes
    @property
    def units(self):
        return self.engine.units

    @property
    def time_str(self):
        return humanize_ms(self.engine.ticktime * self.engine.tick, show_hours=False)

    @property
    def target_crosshair(self):
        return self.engine.get_position(0, value_name=VALUE.TARGET)

    # Logic handlers
    def update(self, gui_size):
        self.gui_size = np.array(gui_size)
        self.view_size = self.gui_size * self.upp

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
                Assets.play_sfx('ui', 'play')
            else:
                Assets.play_sfx('ui', 'pause')

    def user_click(self, target, button):
        if button == 'right':
            aindex = ABILITY_HOTKEYS.index(RIGHT_CLICK_ABILITY)
            self.quickcast(aindex, target)
        elif button == 'left':
            self.user_select(target)
        elif button == 'scrollup':
            self.zoom_out()
        elif button == 'scrolldown':
            self.zoom_in()
        else:
            logger.warning(f'{self.__class__}.user_click() with button: {button} not implemented.')

    def user_select(self, target):
        play_sfx = False
        visible = self.sprite_visible_mask()
        distances = self.engine.get_distances(target)
        uid = NP.argmin(distances, visible)
        dist = distances[uid]
        if dist < 50:
            play_sfx = True
        else:
            uid = 0
        self.select_unit(uid)
        self.draw_unit_selection(uid, play_sfx=play_sfx)

    def draw_unit_selection(self, uid, play_sfx=False, volume='ui'):
        if play_sfx:
            Assets.play_sfx('ui', 'select', volume=volume)
        hb = self.engine.get_stats(uid, STAT.HITBOX)
        self.engine.add_visual_effect(VFX.SPRITE, 60, {
            'uid': uid,
            'fade': 100,
            'category': 'ui',
            'source': 'crosshair2',
            'size': (hb*2.1, hb*2.1),
            'color': (0, 0, 0),
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

    top_panel_color = (1,1,1,1)

    def top_panel_labels(self):
        return ['', '', self.time_str, '']

    @property
    def view_fade(self):
        return (0, 0, 0, 0 if self.engine.auto_tick else 0.5)

    # Sprites and vfx
    map_size = np.full(2, 5_000)
    map_image_source = Assets.FALLBACK_SPRITE
    request_redraw = 0
    def sprite_bar_color(self):
        return (1, 0, 0, 1), (0, 0, .9, 1)

    def sprite_visible_mask(self):
        max_los = self.player_los
        if self.dev_mode:
            max_los = max(max_los, np.linalg.norm(self.view_size) / 2)
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
    menu_text = 'Paused'

    # HUD
    def hud_drag_drop(self, hud, origin, target, button):
        logger.warning(f'{self.__class__}.hud_drag_drop() not implemented. hud: {hud} button: {button} ({origin} -> {target})')

    def hud_click(self, hud, index, button):
        logger.warning(f'{self.__class__}.hud_click() not implemented. hud: {hud} index: {index} button: {button}')
        return SpriteTitleLabel(None, 'Title', f'{self.__class__}.hud_click() not implemented. hud: {hud} index: {index} button: {button}', (0.2, 0, 0, 0.5))

    def hud_portrait_click(self):
        logger.warning(f'{self.__class__}.hud_portrait_click() not implemented.')
        return SpriteTitleLabel(None, 'Title', f'{self.__class__}.hud_portrait_click() not implemented.', (0.2, 0, 0, 0.5))

    def hud_statuses(self):
        return [SpriteBox(None, 'status', (0, 0, 0, 0.5), None) for _ in range(3)]

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
        return [SpriteBox(None, f'{self.__class__}.hud_left() not implemented.', None, None) for _ in range(6)]

    def hud_middle_label(self):
        return f'{self.__class__}.hud_middle_label() not implemented.'

    def hud_middle(self):
        return [SpriteBox(None, f'{self.__class__}.hud_middle() not implemented.', None, None) for _ in range(6)]

    def hud_right(self):
        return [SpriteBox(None, f'{self.__class__}.hud_right() not implemented.', None, None) for _ in range(6)]

    # Browse
    def browse_main(self):
        return SpriteTitleLabel(None, 'Title', f'{self.__class__}.browse_main() not implemented.', (0.2, 0, 0, 0.5))

    def browse_elements(self):
        return [SpriteBox(
            None, f'#{_} {self.__class__}.browse_elements() not implemented.',
            (0.1*_, 0, 1-0.1*_, 0.5), (0,0,0,0)) for _ in range(7)
        ]

    def browse_click(self, index, button):
        logger.warning(f'{self.__class__}.browse_click() not implemented.')
        Assets.play_sfx('ui', 'target')
        return SpriteTitleLabel(str(Assets.FALLBACK_SPRITE), 'Browse', f'{self.__class__}.browse_click() not implemented.', (0,0,0,1))

    def debug_panel_labels(self):
        return [f'{self.__class__}.debug_panel_label() not implemented.']
