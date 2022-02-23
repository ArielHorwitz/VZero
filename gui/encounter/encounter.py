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
from data.settings import Settings
from gui import center_sprite, cc_int, center_position
from gui.api import MOUSE_EVENTS, ControlEvent, InputEvent, CastEvent
from gui.common import Tooltip
from gui.encounter.sprites import Sprites
from gui.encounter.vfx import VFX as VFXLayer
from gui.encounter.panels import Decoration, Menu, LogicLabel, HUD, ModalBrowse, ViewFade, DebugPanel

from logic.common import *


DEFAULT_UPP = 2
MIN_CROSSHAIR_SIZE = (25, 25)


class Encounter(widgets.RelativeLayout):
    OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.timers = defaultdict(RateCounter)
        self.detailed_info_mode = Settings.get_setting('detailed_mode', 'UI')
        self.__units_per_pixel = DEFAULT_UPP
        self.__map_size = np.array([100, 100])
        self.__view_center = np.array([0, 0])
        self.__pix_center = np.array([0, 0])
        self.__holding_mouse = False
        self.__enable_hold_mouse = Settings.get_setting('enable_hold_mouse', 'General') == 1

        # Interface
        self.interface = Interface('GUI Encounter')

        # Setting the order of timers
        for timer in ('draw/idle', 'frame_total', 'graphics_total'):
            self.timers[timer]

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
            'debug': self.add(DebugPanel(enc=self)),
        }
        self.canvas_mouse_input_top = self.add(widgets.Widget())
        self.canvas_mouse_input_top.bind(on_touch_up=self.canvas_release)

        self.make_hotkeys()

        self.interface.register('activate_tooltip', self.activate_tooltip)
        self.interface.register('set_upp', self.set_upp)
        self.interface.register('get_gui_size', self.get_gui_size)
        self.interface.register('get_detailed_info_mode', self.get_detailed_info_mode)
        self.interface.register('set_view_center', self.set_view_center)
        self.interface.register('set_map_source', self.set_map_source)
        self.interface.register('set_move_crosshair', self.set_move_crosshair)
        self.api.setup(self.interface)

    def activate_tooltip(self, stl, pos=None):
        if pos is None:
            pos = self.app.mouse_pos
        self.tooltip.activate(pos, stl)

    def toggle_detailed_info_mode(self, *a, **k):
        self.detailed_info_mode = not self.detailed_info_mode

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
        self.timers['draw/idle'].pong()
        with ratecounter(self.timers['frame_total']):
            self.api.update()
            with ratecounter(self.timers['graphics_total']):
                self._update()
                for timer, frame in self.overlays.items():
                    with ratecounter(self.timers[f'graph_{timer}']):
                        frame.pos = 0, 0
                        frame.update()
        self.timers['draw/idle'].ping()

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
            logger.critical(m)
            raise RuntimeError(m)
        event_name = MOUSE_EVENTS[m.button] if m.button in MOUSE_EVENTS else m.button
        self.interface.append(InputEvent(event_name, self.mouse_real_pos, ''))
        if m.button == 'right' and self.__enable_hold_mouse:
            self.__holding_mouse = True

    def canvas_release(self, w, m):
        if m.button == 'right':
            self.__holding_mouse = False

    def make_hotkeys(self):
        hotkeys = [
            ('toggle_detailed', Settings.get_setting('toggle_detailed', 'Hotkeys'), self.toggle_detailed_info_mode),
        ]
        # Logic API
        api_actions = (
            'toggle_menu', 'toggle_play', 'toggle_shop', 'toggle_map',
            'zoom_in', 'zoom_out', 'reset_view', 'unpan',
            'pan_up', 'pan_down', 'pan_left', 'pan_right',
            'dev1', 'dev2', 'dev3', 'dev4',
        )
        for action_name in api_actions:
            hotkeys.append((
                action_name, Settings.get_setting(action_name, "Hotkeys"),
                lambda action_name_: self.interface.append(ControlEvent(action_name_, self.mouse_real_pos, ''))
            ))
        # Abilities
        alt_mod = Settings.get_setting('alt_modifier', 'Hotkeys')
        hotkeys.append((
            f'loot', Settings.get_setting('loot', 'Hotkeys'),
            lambda *a: self.interface.append(InputEvent('loot', self.mouse_real_pos, ''))))
        for i in range(8):
            akey = Settings.get_setting(f'ability{i+1}', 'Hotkeys')
            ikey = Settings.get_setting(f'item{i+1}', 'Hotkeys')
            if akey:
                if isinstance(akey, float):
                    akey = str(int(akey))
                hotkeys.append((
                    f'ability{i+1}', str(akey),
                    lambda *a, x=i: self.interface.append(CastEvent('ability', x, self.mouse_real_pos, 0, ''))
                ))
                hotkeys.append((
                    f'altability{i+1}', f'{alt_mod} {akey}',
                    lambda *a, x=i: self.interface.append(CastEvent('ability', x, self.mouse_real_pos, 1, ''))
                ))
            if ikey:
                if isinstance(ikey, float):
                    ikey = str(int(ikey))
                hotkeys.append((
                    f'item{i+1}', str(ikey),
                    lambda *a, x=i: self.interface.append(CastEvent('item', x, self.mouse_real_pos, 0, ''))
                ))
                hotkeys.append((
                    f'altitem{i+1}', f'{alt_mod} {ikey}',
                    lambda *a, x=i: self.interface.append(CastEvent('item', x, self.mouse_real_pos, 1, ''))
                ))
        # Register
        for params in hotkeys:
            self.app.enc_hotkeys.register(*params)

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

    def get_detailed_info_mode(self):
        return self.detailed_info_mode

    def set_map_source(self, source=None, size=None):
        if source is not None:
            self.tilemap.source = source
        self.__map_size = size if size is not None else self.__map_size
        logger.info(f'Set map size: {self.__map_size} source: {self.tilemap.source}')

    def set_move_crosshair(self, pos, size=None):
        if size is not None:
            self.move_crosshair.size = cc_int(np.min(np.array([size, MIN_CROSSHAIR_SIZE]), axis=0))
        self.move_crosshair.pos = center_sprite(self.real2pix(pos), self.move_crosshair.size)
