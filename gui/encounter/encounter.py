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
from gui.encounter.sprites import Sprites
from gui.encounter.vfx import VFX
from gui.encounter.panels import Menu, HUD, HUDAux, AgentViewer, Modal, DebugPanel

from engine.common import *


ABILITY_HOTKEYS = Settings.get_setting('abilities', 'Hotkeys')


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
            'hud': self.add(HUD(enc=self)),
            'hud_aux': self.add(HUDAux(enc=self)),
            'agent_panel': self.add(AgentViewer(enc=self)),
            'debug': self.add(DebugPanel(enc=self)),
            'modal': self.add(Modal(enc=self)),
            'menu': self.add(Menu(enc=self)),
        }

        self.simple_overlay_label = self.add(widgets.Label())
        self.simple_overlay_label.set_size(120, 35)

        # User input bindings
        self.app.hotkeys.register_dict({
            # hotkeys
            **{
                name: (Settings.get_setting(name, "Hotkeys"), lambda n=name: self.api.user_hotkey(n, self.mouse_real_pos))
                for name in (
                    'toggle_play', 'toggle_play2', 'toggle_play_dev',
                    'modal1', 'modal2', 'modal3', 'modal4',
                )
            },
            # user controls
            **{f'ability {key.upper()}': (
                f'{key}', lambda *args, x=i: self.api.quickcast(x, self.mouse_real_pos)
                ) for i, key in enumerate(ABILITY_HOTKEYS)},
            # debug
            'toggle dev mode': (f'^+ d', lambda: self.api.debug(dev_mode=None)),
            'normal tps': (f'^+ t', lambda: self.api.debug(tps=120)),
            'high tps': (f'^!+ t', lambda: self.api.debug(tps=920)),
            'single tick': (f'^ t', lambda: self.api.debug(tick=1)),
            # gui view controls
            'zoom default': (
                f'{Settings.get_setting("zoom_default", "Hotkeys")}',
                lambda: self.set_zoom()),
            'zoom in': (
                f'{Settings.get_setting("zoom_in", "Hotkeys")}',
                lambda: self.set_zoom(d=1.15)),
            'zoom out': (
                f'{Settings.get_setting("zoom_out", "Hotkeys")}',
                lambda: self.set_zoom(d=-1.15)),
            'map view': (
                f'{Settings.get_setting("map_view", "Hotkeys")}',
                lambda: self.toggle_map_zoom()),
            'redraw map': (f'^+ r', lambda: self.redraw_map()),
            })

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
            self.api.user_click(self.__cached_target, button='right', view_size=self.real2pix(self.size))
            self.__cached_target = None
        self.__player_pos = player_pos = self.api.view_center
        self.__anchor_offset = np.array(self.size) / 2

        self.simple_overlay_label.pos = cc_int(np.array(self.size) - np.array(self.simple_overlay_label.size))
        self.simple_overlay_label.text = f'{round(self.app.fps.rate)} FPS | {self.api.time_str}'
        self.simple_overlay_label.make_bg(self.app.fps_color)

        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))
        self.tilemap.size = cc_int(np.array(self.api.map_size) / self.__units_per_pixel)

        self.target_crosshair.pos = center_position(self.real2pix(
            self.api.target_crosshair), self.target_crosshair.size)

        if self.api.request_redraw != self.__last_redraw:
            self.__last_redraw = self.api.request_redraw
            self.redraw_map()

    # User Input
    def canvas_move(self, w, m):
        if m.button == 'right' and Settings.get_setting('enable_hold_mouse', 'Hotkeys'):
            self.__cached_target = self.mouse_real_pos

    def canvas_click(self, w, m):
        # TODO expose top corner click to API
        if self.collide_corners(m.pos):
            self.api.user_hotkey('toggle_play', self.pix2real(np.array(self.size)/2))
            return True
        if not self.collide_point(*m.pos):
            return False
        self.api.user_click(self.pix2real(m.pos), m.button, self.pix2real(self.size))

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
