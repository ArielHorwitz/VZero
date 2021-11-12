import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np
from collections import defaultdict
from nutil.vars import nsign
from nutil.time import RateCounter, ratecounter
from nutil.kex import widgets

from data.load import Settings, Assets
from data.tileset import TileMap
from gui import cc_int
from gui.encounter.sprites import Sprites
from gui.encounter.vfx import VFX
from gui.encounter.hud import HUD
from gui.encounter.panels import InfoPanel, DebugPanel

from logic.mechanics.common import *


class Encounter(widgets.RelativeLayout):
    DEFAULT_UPP = 1 / Settings.get_setting('zoom')

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.timers = defaultdict(RateCounter)
        self.__units_per_pixel = self.DEFAULT_UPP
        self.__cached_move = None
        self.selected_unit = 0
        self._music_track = Assets.get_sfx('theme', 'theme')
        self.toggle_theme()

        # Setting the order of timers
        for timer in ('draw/idle', 'frame_total', 'graphics_total'):
            self.timers[timer]

        ability_hotkeys = enumerate(Settings.get_setting('ability_hotkeys'))

        # User input bindings
        self.app.hotkeys.register_dict({
            # encounter management
            'toggle pause': (f' spacebar', lambda: self.toggle_play()),
            'leave encounter': (f' escape', lambda: self.app.end_encounter()),
            # debug
            'debug': (f'^+ d', lambda: self.debug()),
            'debug dmod': (f'^+ v', lambda: self.debug(dmod=True)),
            'normal tps': (f'^+ t', lambda: self.debug(tps=None)),
            'high tps': (f'^!+ t', lambda: self.debug(tps=920)),
            'single tick': (f'^ t', lambda: self.debug(tick=1)),
            # user controls
            **{f'ability {key.upper()}': (
                f' {key}', lambda *args, x=i: self.quickcast(x)
                ) for i, key in ability_hotkeys},
            'toggle range': (f'! r', lambda: self.set_draw_range()),
            'zoom default': (f' 0', lambda: self.zoom()),
            'zoom in': (f' =', lambda: self.zoom(d=1.15)),
            'zoom out': (f' -', lambda: self.zoom(d=-1.15)),
            })
        self.bind(on_touch_down=self.do_mouse_down)
        self.bind(on_touch_move=self.check_mouse_move)

        # DRAW
        self.redraw()
        self.sprites = self.add(Sprites(enc=self))
        self.vfx = self.add(VFX(enc=self))
        self.hud = self.add(HUD(anchor_y='bottom', enc=self))
        self.info_panel = self.add(InfoPanel(anchor_x='left', anchor_y='top', enc=self))
        self.debug_panel = self.add(DebugPanel(anchor_x='right', anchor_y='top', enc=self))
        self.sub_frames = {
            'sprites': self.sprites,
            'vfx': self.vfx,
            'hud': self.hud,
            'info': self.info_panel,
            'debug': self.debug_panel,
        }

    def redraw(self):
        self.canvas.clear()

        tilemap_source = self.__tilemap_source = TileMap(
            ['tiles1']).make_map(100, 100)
        tilemap_size = list(self.api.map_size / self.__units_per_pixel)
        with self.canvas.before:
            # Tilemap
            self.tilemap = widgets.Image(
               source=tilemap_source,
               allow_stretch=True,
               size=cc_int(tilemap_size),
           )

    def toggle_play(self):
        self.api.set_auto_tick()
        self.toggle_theme()

    def toggle_theme(self):
        if self.api.auto_tick is True:
            logger.debug(f'Playing theme {self._music_track}')
            self._music_track.play(loop=True, replay=False, volume=Settings.get_setting('volume_music'))
        else:
            logger.debug(f'Pausing theme {self._music_track}')
            self._music_track.pause()

    def update(self):
        self.timers['draw/idle'].pong()

        with ratecounter(self.timers['frame_total']):
            self.api.update()
            self._update()
            with ratecounter(self.timers['graphics_total']):
                for timer, frame in self.sub_frames.items():
                    with ratecounter(self.timers[timer]):
                        frame.pos = 0, 0
                        frame.update()

        self.timers['draw/idle'].ping()

    def _update(self):
        if self.__cached_move is not None:
            self.use_ability(
                self.api.units[0].ability_order[5],
                self.__cached_move, supress_sfx=True)
            self.__cached_move = None
        player_pos = self.api.get_position(0)
        self.__player_pos = player_pos
        self.__anchor_offset = np.array(self.size) / 2

        self.tilemap.size = cc_int(np.array(self.api.map_size) / self.__units_per_pixel)
        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))

    def debug(self, *a, **k):
        return self.api.debug(*a, **k)

    def check_mouse_move(self, w, m):
        if m.button == 'right':
            self.__cached_move = self.mouse_real_pos

    def do_mouse_down(self, w, m):
        if not self.collide_point(*m.pos):
            return
        real_pos = self.mouse_real_pos
        if m.button == 'right':
            self.use_ability(self.api.units[0].ability_order[5], real_pos)
        if m.button == 'left':
            selected_unit = self.api.nearest_uid(real_pos, alive=False)[0]
            self.info_panel.select_unit(selected_unit)

    @property
    def zoom_level(self):
        return 1 / self.__units_per_pixel

    # Utility
    def quickcast(self, key_index):
        ao = self.api.units[0].ability_order
        if key_index >= len(ao):
            return
        a = ao[key_index]
        if a is None:
            return
        self.use_ability(ao[key_index], self.mouse_real_pos)

    def use_ability(self, aid, target, supress_sfx=False):
        if not self.api.auto_tick:
            return
        r = self.api.units[0].use_ability(self.api, aid, target)
        if supress_sfx == False:
            if r is FAIL_RESULT.MISSING_COST:
                # print(f'Missing cost for {aid.name}')
                Assets.play_sfx('ui', 'cost', volume=Settings.get_setting('volume_feedback'))
            if r is FAIL_RESULT.MISSING_TARGET:
                # print(f'Missing target for {aid.name}')
                Assets.play_sfx('ui', 'target', volume=Settings.get_setting('volume_feedback'))
            if r is FAIL_RESULT.OUT_OF_BOUNDS:
                # print('Out of bounds')
                Assets.play_sfx('ui', 'range', volume=Settings.get_setting('volume_feedback'))
            if r is FAIL_RESULT.OUT_OF_RANGE:
                # print(f'Out of range for {aid.name}')
                Assets.play_sfx('ui', 'range', volume=Settings.get_setting('volume_feedback'))
            if r is FAIL_RESULT.ON_COOLDOWN:
                # print(f'{aid.name} on cooldown')
                Assets.play_sfx('ui', 'cooldown', volume=Settings.get_setting('volume_feedback'))
        return r

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
    def upp(self):
        return self.__units_per_pixel

    @property
    def mouse_real_pos(self):
        local = self.to_local(*self.app.mouse_pos)
        real = self.pix2real(local)
        return real

    def zoom(self, d=None):
        if d is None:
            self.__units_per_pixel = self.DEFAULT_UPP
        else:
            self.__units_per_pixel *= abs(d)**(-1*nsign(d))


OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)
