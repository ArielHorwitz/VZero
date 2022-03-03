import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from collections import defaultdict
from nutil.vars import nsign, minmax, Interface
from nutil.time import RateCounter, ratecounter
from nutil.kex import widgets

from data.assets import Assets
from data.settings import PROFILE, GLOBAL_CANCEL_KEY
from gui import center_sprite, cc_int, center_position
from gui.api import MOUSE_EVENTS, ControlEvent, InputEvent, CastEvent
from gui.common import Tooltip
from gui.encounter.sprites import Sprites
from gui.encounter.vfx import VFX as VFXLayer
from gui.encounter.panels import ControlButton, Menu, LogicLabel, ViewFade, Decoration
from gui.encounter.panels import HUD, ModalBrowse, DebugPanel

from logic.common import *


DEFAULT_UPP = 2
MIN_CROSSHAIR_SIZE = (25, 25)


class Encounter(widgets.RelativeLayout):
    OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.settings_notifier = self.api.settings_notifier
        self.total_timers = defaultdict(RateCounter)
        self.single_timers = defaultdict(RateCounter)
        self.__units_per_pixel = DEFAULT_UPP
        self.__map_size = np.array([100, 100])
        self.__view_center = np.array([0, 0])
        self.__pix_center = np.array([0, 0])
        self.__holding_mouse = False
        self.settings_notifier.subscribe('general.enable_hold_mouse', self.setting_enable_hold_mouse)
        self.setting_enable_hold_mouse()

        # Interface
        self.interface = Interface('GUI Encounter')

        # DRAW
        self.draw()
        # Create a widget to handle mouse input for the bottom layer
        # such that other widgets may take priority and consume the
        # mouse event (but mouse release should always be caught).
        self.canvas_mouse_input_bottom = self.add(widgets.Widget())
        self.canvas_mouse_input_bottom.bind(on_touch_down=self.canvas_click)
        self.overlays = {
            'sprites': self.add(Sprites(enc=self)),
            'vfx': self.add(VFXLayer(enc=self)),
            'viewfade': self.add(ViewFade(enc=self)),
        }
        self.decorations = self.add(Decoration(enc=self))
        self.overlays |= {
            'logic_label': self.add(LogicLabel(enc=self)),
            'modal_browse': self.add(ModalBrowse(enc=self)),
            'hud': self.add(HUD(enc=self)),
        }
        self.tooltip = self.add(Tooltip(bounding_widget=self))
        self.overlays |= {
            'menu': self.add(Menu(enc=self)),
            'menu_button': self.add(ControlButton(enc=self)),
            'debug': self.add(DebugPanel(enc=self)),
        }
        self.canvas_mouse_input_top = self.add(widgets.Widget())
        self.canvas_mouse_input_top.bind(on_touch_up=self.canvas_release)

        hotkeys = self.make_hotkeys()
        for action, k, c in hotkeys:
            self.settings_notifier.subscribe(f'hotkeys.{action}', self.make_hotkeys)
        self.settings_notifier.subscribe(f'hotkeys.alt_modifier', self.make_hotkeys)

        self.interface.register('activate_tooltip', self.activate_tooltip)
        self.interface.register('deactivate_tooltip', self.tooltip.deactivate)
        self.interface.register('set_upp', self.set_upp)
        self.interface.register('get_gui_size', self.get_gui_size)
        self.interface.register('get_mouse_pos', lambda: self.mouse_real_pos)
        self.interface.register('set_view_center', self.set_view_center)
        self.interface.register('set_map_source', self.set_map_source)
        self.interface.register('set_move_crosshair', self.set_move_crosshair)
        self.api.setup(self.interface)

    def activate_tooltip(self, stl, pos=None):
        if pos is None:
            pos = self.app.mouse_pos
        self.tooltip.activate(pos, stl)

    def setting_enable_hold_mouse(self):
        self.__enable_hold_mouse = PROFILE.get_setting('general.enable_hold_mouse')

    def draw(self):
        self.canvas.clear()

        with self.canvas.before:
            # Tilemap
            self.tilemap = widgets.kvRectangle()

        # Move target indicator
        with self.canvas:
            widgets.kvColor(0, 0, 0)
            self.move_crosshair = widgets.kvRectangle(
                source=Assets.get_sprite('ui.crosshair-move'),
                allow_stretch=True, size=MIN_CROSSHAIR_SIZE)
            widgets.kvColor(1, 1, 1)

    def update(self):
        self.total_timers['draw/idle'].pong()
        with self.total_timers['frame_total'].time_block:
            self.api.update()
            with self.total_timers['graphics_total'].time_block:
                self._update()
                for timer, frame in self.overlays.items():
                    with self.total_timers[f'{timer}'].time_block:
                        frame.pos = 0, 0
                        frame.update()
        self.total_timers['draw/idle'].ping()

    def _update(self):
        if self.__holding_mouse:
            self.interface.append(InputEvent(MOUSE_EVENTS['right'], self.mouse_real_pos, ''))
        self.__pix_center_offset = np.array([0, (self.overlays['hud'].overlay_height - self.overlays['logic_label'].overlay_height)/2])
        self.__pix_center = (np.array(self.size) / 2) + self.__pix_center_offset

        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))
        self.tilemap.size = cc_int(self.__map_size / self.upp)

    # User Input
    def canvas_click(self, w, m):
        if not self.collide_point(*m.pos):
            return False
        if not isinstance(m.button, str):
            m = f'canvas_click m.button not a str: {m.button} mouse ctx: {m}'
            logger.warning(m)
            # Used to raise an exception for this but kivy has sent MouseMotionEvents
            # here even though we are bound to `on_mouse_down`...
            # It seems that somehow pressing/holding alt while pressing/holding left mouse will reproduce this error
            # Or possibly disabling `detailed_mode` while holding left mouse will reproduce this error
            return
        event_name = MOUSE_EVENTS[m.button] if m.button in MOUSE_EVENTS else m.button
        self.interface.append(InputEvent(event_name, self.mouse_real_pos, ''))
        if m.button == 'right' and self.__enable_hold_mouse:
            self.__holding_mouse = True

    def canvas_release(self, w, m):
        if m.button == 'right':
            self.__holding_mouse = False

    def make_hotkeys(self):
        logger.info(f'EGUI making hotkeys...')
        self.app.enc_hotkeys.clear_all()
        hotkeys = [
            ('toggle_menu', GLOBAL_CANCEL_KEY, lambda *a: self.interface.append(ControlEvent('toggle_menu', self.mouse_real_pos, ''))),
        ]
        # Logic API
        api_actions = (
            'toggle_play', 'toggle_shop', 'toggle_map',
            'zoom_in', 'zoom_out', 'reset_view', 'unpan',
            'pan_up', 'pan_down', 'pan_left', 'pan_right',
            'dev1', 'dev2', 'dev3',
        )
        for action_name in api_actions:
            hotkeys.append((
                action_name, PROFILE.get_setting(f'hotkeys.{action_name}'),
                lambda action_name_: self.interface.append(ControlEvent(action_name_, self.mouse_real_pos, ''))
            ))
        # Abilities
        alt_mod_name = PROFILE.get_setting('hotkeys.alt_modifier').lower()
        alt_mod = widgets.InputManager.MODIFIERS[alt_mod_name.lower()]
        hotkeys.append((
            f'loot', PROFILE.get_setting('hotkeys.loot'),
            lambda *a: self.interface.append(InputEvent('loot', self.mouse_real_pos, ''))))
        for i in range(8):
            akey = PROFILE.get_setting(f'hotkeys.ability_{i+1}')
            ikey = PROFILE.get_setting(f'hotkeys.item_{i+1}')
            if akey:
                if isinstance(akey, float):
                    akey = str(int(akey))
                hotkeys.append((
                    f'ability_{i+1}', str(akey),
                    lambda *a, x=i: self.interface.append(CastEvent('ability', x, self.mouse_real_pos, 0, ''))
                ))
                hotkeys.append((
                    f'altability_{i+1}', f'{alt_mod} {akey}',
                    lambda *a, x=i: self.interface.append(CastEvent('ability', x, self.mouse_real_pos, 1, ''))
                ))
            if ikey:
                if isinstance(ikey, float):
                    ikey = str(int(ikey))
                hotkeys.append((
                    f'item_{i+1}', str(ikey),
                    lambda *a, x=i: self.interface.append(CastEvent('item', x, self.mouse_real_pos, 0, ''))
                ))
                hotkeys.append((
                    f'altitem_{i+1}', f'{alt_mod} {ikey}',
                    lambda *a, x=i: self.interface.append(CastEvent('item', x, self.mouse_real_pos, 1, ''))
                ))
        # Register
        for params in hotkeys:
            self.app.enc_hotkeys.register(*params)
        return hotkeys

    # Utility
    def real2pix(self, pos):
        pos_relative_to_center = np.array(pos) - self.__view_center
        pix_relative_to_center = pos_relative_to_center / self.upp
        return self.__pix_center + pix_relative_to_center

    def pix2real(self, pix):
        pix_relative_to_center = np.array(pix) - self.__pix_center
        real_relative_to_center = pix_relative_to_center * self.upp
        return self.__view_center + real_relative_to_center

    @property
    def view_size(self):
        return np.array(self.size) * self.upp

    @property
    def upp(self):
        return self.__units_per_pixel

    @property
    def mouse_real_pos(self):
        local = self.to_local(*self.app.mouse_pos)
        real = self.pix2real(local)
        return real

    @property
    def zoom_str(self):
        return f'{round(100 / self.upp)}%'

    # Interface
    def set_upp(self, upp):
        self.__units_per_pixel = upp

    def set_view_center(self, real_pos):
        self.__view_center = real_pos

    def get_gui_size(self):
        overlay_height = self.overlays['hud'].overlay_height + self.overlays['logic_label'].overlay_height
        usable_view_size = np.array(self.size) - [0, overlay_height]
        return usable_view_size

    def set_map_source(self, source=None, size=None):
        if source is not None:
            self.tilemap.source = source
        self.__map_size = size if size is not None else self.__map_size
        logger.info(f'Set map size: {self.__map_size} source: {self.tilemap.source}')

    def set_move_crosshair(self, pos, size=None):
        if size is not None:
            self.move_crosshair.size = cc_int(np.min(np.array([size, MIN_CROSSHAIR_SIZE]), axis=0))
        self.move_crosshair.pos = center_sprite(self.real2pix(pos), self.move_crosshair.size)
