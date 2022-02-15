import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from collections import defaultdict
from nutil.vars import nsign, minmax
from nutil.time import RateCounter, ratecounter
from nutil.kex import widgets

from data.assets import Assets
from data.settings import Settings
from gui import cc_int, center_position
from gui.common import Tooltip
from gui.encounter.sprites import Sprites
from gui.encounter.vfx import VFX as VFXLayer
from gui.encounter.panels import Decoration, Menu, LogicLabel, HUD, ModalBrowse, ViewFade, DebugPanel

from engine.common import *


class Encounter(widgets.RelativeLayout):
    OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)
    MIN_CROSSHAIR_SIZE = (25, 25)
    DEFAULT_UPP = 2

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.timers = defaultdict(RateCounter)
        self.detailed_info_mode = False
        self.__units_per_pixel = self.DEFAULT_UPP
        self.__holding_mouse = False
        self.__enable_hold_mouse = Settings.get_setting('enable_hold_mouse', 'Hotkeys') == 1
        self.__last_redraw = -1

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

    def toggle_detailed_info_mode(self, *a, **k):
        self.detailed_info_mode = not self.detailed_info_mode

    def redraw_map(self):
        self.tilemap.source = str(self.api.map_image_source)
        logger.info(f'Redraw map: {self.tilemap.source}')

    def draw(self):
        self.canvas.clear()

        with self.canvas.before:
            # Tilemap
            self.tilemap = widgets.kvRectangle()
            self.redraw_map()

        # Move target indicator
        with self.canvas:
            widgets.kvColor(0, 0, 0)
            self.move_crosshair = widgets.kvRectangle(
                source=Assets.get_sprite('ui', 'crosshair-move'),
                allow_stretch=True, size=self.MIN_CROSSHAIR_SIZE)
            widgets.kvColor(1, 1, 1)

    def update(self):
        self.timers['draw/idle'].pong()

        with ratecounter(self.timers['frame_total']):
            overlay_height = self.overlays['hud'].overlay_height + self.overlays['logic_label'].overlay_height
            usable_view_size = np.array(self.size) - [0, overlay_height]
            self.api.update(usable_view_size, self.detailed_info_mode)
            with ratecounter(self.timers['graphics_total']):
                self._update()
                for timer, frame in self.overlays.items():
                    with ratecounter(self.timers[f'graph_{timer}']):
                        frame.pos = 0, 0
                        frame.update()

        self.timers['draw/idle'].ping()

    def _update(self):
        if self.__holding_mouse:
            self.api.user_click(self.mouse_real_pos, button='right')
        self.__view_center = self.api.view_center
        self.__pix_center_offset = np.array([0, (self.overlays['hud'].overlay_height - self.overlays['logic_label'].overlay_height)/2])
        self.__pix_center = (np.array(self.size) / 2) + self.__pix_center_offset

        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))
        self.tilemap.size = cc_int(np.array(self.api.map_size) / self.upp)

        self.move_crosshair.size = cc_int(np.min(np.array(
            [self.api.move_crosshair_size, self.MIN_CROSSHAIR_SIZE]), axis=0))
        self.move_crosshair.pos = center_position(self.real2pix(
            self.api.move_crosshair_pos), self.move_crosshair.size)

        if self.api.request_redraw != self.__last_redraw:
            self.__last_redraw = self.api.request_redraw
            self.redraw_map()

    # User Input
    def canvas_click(self, w, m):
        if not self.collide_point(*m.pos):
            return False
        self.api.user_click(self.pix2real(m.pos), m.button)
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
            'toggle_play', 'toggle_map', 'zoom_in', 'zoom_out', 'reset_view',
            'pan_up', 'pan_down', 'pan_left', 'pan_right',
            'control0', 'control1', 'control2', 'control3', 'control4',
            'dev1', 'dev2', 'dev3', 'dev4',
        )
        for action_name in api_actions:
            hotkeys.append((
                action_name, Settings.get_setting(action_name, "Hotkeys"),
                lambda action_name_: self.api.user_hotkey(action_name_, self.mouse_real_pos)
            ))
        # Abilities
        hotkeys.append((
            f'loot', Settings.get_setting('loot', 'Hotkeys'),
            lambda *a: self.api.lootcast(self.mouse_real_pos)))
        alt_mod = Settings.get_setting('alt_modifier', 'Hotkeys')
        for i, key in enumerate(Settings.get_setting('abilities', 'Hotkeys')):
            hotkeys.append((
                f'ability {key.upper()}', key,
                lambda *a, x=i: self.api.quickcast(x, self.mouse_real_pos)
            ))
            hotkeys.append((
                f'ability alt {key.upper()}', f'{alt_mod} {key}',
                lambda *a, x=i: self.api.quickcast(x, self.mouse_real_pos, alt=1)
            ))
        # Items
        for i, key in enumerate(Settings.get_setting('items', 'Hotkeys')):
            hotkeys.append((
                f'item {key.upper()} ability', key,
                lambda *a, x=i: self.api.itemcast(x, self.mouse_real_pos)
            ))
            hotkeys.append((
                f'item alt {key.upper()}', f'{alt_mod} {key}',
                lambda *a, x=i: self.api.itemcast(x, self.mouse_real_pos, alt=1)
            ))
        # View control
        hotkeys.extend([
            ('redraw map', f'f5', lambda *a: self.redraw_map()),
        ])
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
        return self.api.upp

    @property
    def mouse_real_pos(self):
        local = self.to_local(*self.app.mouse_pos)
        real = self.pix2real(local)
        return real

    @property
    def zoom_str(self):
        return f'{round(100 / self.upp)}%'
