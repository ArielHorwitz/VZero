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
from gui.encounter.vfx import VFX
from gui.encounter.panels import Menu, ControlOverlay, LogicLabel, HUD, ModalBrowse, DebugPanel

from engine.common import *


class Encounter(widgets.RelativeLayout):
    OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)
    DEFAULT_UPP = 1 / Settings.get_setting('default_zoom')

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.timers = defaultdict(RateCounter)
        self.__units_per_pixel = self.DEFAULT_UPP
        self.__cached_target = None
        self.__last_redraw = -1

        # Setting the order of timers
        for timer in ('draw/idle', 'frame_total', 'graphics_total'):
            self.timers[timer]

        # DRAW
        self.draw()
        # Create a widget to handle mouse input for the bottom layer
        # such that other widgets may take priority and consume the
        # mouse event.
        self.canvas_mouse_input = self.add(widgets.Widget())
        self.canvas_mouse_input.bind(
            on_touch_down=self.canvas_click,
            on_touch_move=self.canvas_move,
        )
        self.overlays = {
            'sprites': self.add(Sprites(enc=self)),
            'vfx': self.add(VFX(enc=self)),
            'logic_label': self.add(LogicLabel(enc=self)),
            'modal_browse': self.add(ModalBrowse(enc=self)),
            'hud': self.add(HUD(enc=self)),
        }
        self.tooltip = self.add(Tooltip(bounding_widget=self))
        self.overlays['control_overlay'] = self.add(ControlOverlay(enc=self))
        self.overlays['menu'] = self.add(Menu(enc=self))
        self.overlays['debug'] = self.add(DebugPanel(enc=self))

        self.make_hotkeys()

    def redraw_map(self):
        self.tilemap.source = str(self.api.map_image_source)
        logger.info(f'Redraw map: {self.tilemap.source}')

    def draw(self):
        self.canvas.clear()

        tilemap_size = list(self.api.map_size / self.__units_per_pixel)
        with self.canvas.before:
            # Tilemap
            self.tilemap = widgets.kvRectangle()
            self.redraw_map()

        # Move target indicator
        with self.canvas:
            widgets.kvColor(1, 1, 1)
            self.target_crosshair = widgets.kvRectangle(
                source=Assets.get_sprite('ui', 'crosshair3'),
                allow_stretch=True, size=(15, 15))

    def update(self):
        self.timers['draw/idle'].pong()

        with ratecounter(self.timers['frame_total']):
            self.api.update()
            self._update()
            with ratecounter(self.timers['graphics_total']):
                for timer, frame in self.overlays.items():
                    with ratecounter(self.timers[f'graph_{timer}']):
                        frame.pos = 0, 0
                        frame.update()

        self.timers['draw/idle'].ping()

    def _update(self):
        if self.__cached_target is not None:
            self.api.user_click(self.__cached_target, button='right', view_size=self.pix2real(self.size))
            self.__cached_target = None
        self.__player_pos = player_pos = self.api.view_center
        self.__anchor_offset = np.array(self.size) / 2



        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))
        self.tilemap.size = cc_int(np.array(self.api.map_size) / self.__units_per_pixel)

        self.target_crosshair.pos = center_position(self.real2pix(
            self.api.target_crosshair), self.target_crosshair.size)

        if self.api.request_redraw != self.__last_redraw:
            self.__last_redraw = self.api.request_redraw
            self.redraw_map()

    # User Input
    def canvas_move(self, w, m):
        if m.button == 'right' and Settings.get_setting('enable_hold_mouse', 'Hotkeys') == 1:
            self.__cached_target = self.mouse_real_pos

    def canvas_click(self, w, m):
        # TODO expose top corner click to API
        if self.collide_corners(m.pos):
            self.api.user_hotkey('toggle_play', self.pix2real(np.array(self.size)/2))
            return True
        if not self.collide_point(*m.pos):
            return False
        self.api.user_click(self.pix2real(m.pos), m.button, self.pix2real(self.size))

    def make_hotkeys(self):
        hotkeys = []
        # Logic API
        api_actions = (
            'toggle_play',
            'control0', 'control1', 'control2', 'control3', 'control4',
            'dev1', 'dev2', 'dev3', 'dev4',
        )
        for action_name in api_actions:
            hotkeys.append((
                action_name,
                Settings.get_setting(action_name, "Hotkeys"),
                lambda action_name_: self.api.user_hotkey(action_name_, self.mouse_real_pos)
            ))
        # Abilities
        for i, key in enumerate(Settings.get_setting('abilities', 'Hotkeys')):
            hotkeys.append((
                f'ability {key.upper()}',
                key,
                lambda *a, x=i: self.api.quickcast(x, self.mouse_real_pos)
            ))
        # Items
        for i, key in enumerate(Settings.get_setting('items', 'Hotkeys')):
            hotkeys.append((
                f'item {key.upper()} ability',
                key,
                lambda *a, x=i: self.api.itemcast(x, self.mouse_real_pos)
            ))
        # View control
        hotkeys.extend([
            ('zoom default', f'{Settings.get_setting("zoom_default", "Hotkeys")}', lambda *a: self.set_zoom()),
            ('zoom in', f'{Settings.get_setting("zoom_in", "Hotkeys")}', lambda *a: self.set_zoom(d=1.15)),
            ('zoom out', f'{Settings.get_setting("zoom_out", "Hotkeys")}', lambda *a: self.set_zoom(d=-1.15)),
            ('map view', f'{Settings.get_setting("map_view", "Hotkeys")}', lambda *a: self.toggle_map_zoom()),
            ('redraw map', f'f5', lambda *a: self.redraw_map()),
        ])
        # Register
        for params in hotkeys:
            self.app.enc_hotkeys.register(*params)

    # Control
    def toggle_map_zoom(self):
        if self.__units_per_pixel == self.DEFAULT_UPP:
            self.set_zoom(Settings.get_setting('map_zoom', 'General'))
        else:
            logger.debug(f'Setting to default upp')
            self.set_zoom()

    def set_zoom(self, d=None, v=None):
        if v is not None:
            self.__units_per_pixel = v
            return
        if d is None:
            self.__units_per_pixel = self.DEFAULT_UPP
        else:
            self.__units_per_pixel *= abs(d)**(-1*nsign(d))

    # Utility
    def real2pix(self, pos):
        pos_relative_to_player = np.array(pos) - self.__player_pos
        pix_relative_to_player = pos_relative_to_player / self.__units_per_pixel
        final_pos = pix_relative_to_player + self.__anchor_offset
        return final_pos

    def pix2real(self, pix):
        pix_relative_to_player = np.array(pix) - (np.array(self.size) / 2)
        real_relative_to_player = pix_relative_to_player * self.__units_per_pixel
        real_position = self.__player_pos + real_relative_to_player
        return real_position

    @property
    def map_mode(self):
        return self.upp > 4

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

    def collide_corners(self, pos):
        margin = 0.01
        return any([
            pos[1] > self.size[1]*(1-margin),
            pos[1] < self.size[1]*margin,
        ]) and any([
            pos[0] > self.size[0]*(1-margin),
            pos[0] < self.size[0]*margin,
        ])

    @property
    def zoom_level(self):
        return 1 / self.__units_per_pixel
