import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from collections import defaultdict
from nutil.vars import nsign, minmax
from nutil.time import RateCounter, ratecounter, humanize_ms
from nutil.kex import widgets

from data.assets import Assets
from data.settings import Settings
from gui import cc_int, center_position
from gui.encounter.sprites import Sprites
from gui.encounter.vfx import VFX
from gui.encounter.hud import HUD
from gui.encounter.panels import AgentViewer, DebugPanel
from gui.encounter.menu.menu import Menu

from logic.mechanics.common import *


class Encounter(widgets.RelativeLayout):
    OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)
    DEFAULT_UPP = 1 / Settings.get_setting('default_zoom')

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.api = api
        self.selected_unit = 0
        self.timers = defaultdict(RateCounter)
        self.__units_per_pixel = self.DEFAULT_UPP
        self.__cached_target = None
        self.selected_unit = 0
        self._theme_track = Assets.get_sfx('theme', 'theme')
        self.toggle_play_sounds()

        # Setting the order of timers
        for timer in ('draw/idle', 'frame_total', 'graphics_total'):
            self.timers[timer]

        # DRAW
        self.redraw()
        self.sprites = self.add(Sprites(enc=self))
        self.vfx = self.add(VFX(enc=self))
        self.hud = self.add(HUD(anchor_y='bottom', enc=self))
        self.agent_panel = self.add(AgentViewer(anchor_x='left', anchor_y='top', enc=self))
        self.debug_panel = self.add(DebugPanel(anchor_x='right', anchor_y='top', enc=self))
        self.enc_menu = Menu(enc=self)
        self.sub_frames = {
            'sprites': self.sprites,
            'vfx': self.vfx,
            'hud': self.hud,
            'agent_panel': self.agent_panel,
            'debug': self.debug_panel,
            'menu': self.enc_menu,
        }

        self.ability_hotkeys = Settings.get_setting('abilities', 'Hotkeys')
        self.right_click_ability = Settings.get_setting('right_click', 'Hotkeys')
        self.overlay_label = self.add(widgets.Label())
        self.overlay_label.set_size(120, 35)

        # User input bindings
        self.app.hotkeys.register_dict({
            # encounter management
            'toggle play/pause': (
                f'{Settings.get_setting("toggle_play", "Hotkeys")}',
                lambda: self.toggle_play()),
            'toggle play/pause2': (
                f'{Settings.get_setting("toggle_play2", "Hotkeys")}',
                lambda: self.toggle_play()),
            # user controls
            **{f'ability {key.upper()}': (
                f'{key}', lambda *args, x=i: self.quickcast(x)
                ) for i, key in enumerate(self.ability_hotkeys)},
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
            # debug
            # 'debug': (f'^+ d', lambda: self.debug()),
            'toggle play/pause dev': (
                f'{Settings.get_setting("toggle_play_dev", "Hotkeys")}',
                lambda: self.toggle_play(show_menu=False)),
            'toggle dev mode': (f'^+ d', lambda: self.api.debug(dev_mode=None)),
            'normal tps': (f'^+ t', lambda: self.api.debug(tps=None)),
            'high tps': (f'^!+ t', lambda: self.api.debug(tps=920)),
            'single tick': (f'^ t', lambda: self.api.debug(tick=1)),
            })
        self.bind(on_touch_down=self.do_mouse_down)
        self.bind(on_touch_move=self.check_mouse_move)

    def redraw(self):
        self.canvas.clear()

        tilemap_source = self.api.map_image_source
        tilemap_size = list(self.api.map_size / self.__units_per_pixel)
        with self.canvas.before:
            # Tilemap
            self.tilemap = widgets.Image(
               source=str(tilemap_source),
               allow_stretch=True)

        # Move target indicator
        with self.canvas:
            widgets.kvColor(1, 1, 1)
            self.move_crosshair = widgets.kvRectangle(
                source=Assets.get_sprite('ui', 'crosshair3'),
                allow_stretch=True, size=(15, 15))

    def update(self):
        self.timers['draw/idle'].pong()

        with ratecounter(self.timers['frame_total']):
            self.api.update()
            self._update()
            with ratecounter(self.timers['graphics_total']):
                for timer, frame in self.sub_frames.items():
                    with ratecounter(self.timers[f'graph_{timer}']):
                        frame.pos = 0, 0
                        frame.update()

        self.timers['draw/idle'].ping()

    def _update(self):
        if self.__cached_target is not None:
            if Settings.get_setting('enable_hold_mouse', 'Hotkeys'):
                self.use_right_click()
            self.__cached_target = None
        player_pos = self.api.get_position(0)
        self.__player_pos = player_pos
        self.__anchor_offset = np.array(self.size) / 2

        self.overlay_label.pos = cc_int(np.array(self.size) - np.array(self.overlay_label.size))
        self.overlay_label.text = f'{round(self.app.fps.rate)} FPS | {humanize_ms(self.api.elapsed_time_ms)}'
        self.overlay_label.make_bg(self.app.fps_color)

        self.tilemap.size = cc_int(np.array(self.api.map_size) / self.__units_per_pixel)
        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))

        self.move_crosshair.pos = center_position(self.real2pix(
            self.api.get_position(0, value_name=VALUE.TARGET_VALUE)
            ), self.move_crosshair.size)

    # User Input
    def check_mouse_move(self, w, m):
        if m.button == 'right':
            self.__cached_target = self.mouse_real_pos

    def do_mouse_down(self, w, m):
        if self.collide_top_corners(m.pos):
            self.toggle_play()
            return True
        if not self.collide_point(*m.pos):
            return False
        if m.button == 'right':
            self.use_right_click(m.pos)
        if m.button == 'left':
            self.use_left_click(m.pos)

    def use_left_click(self, point=None):
        point = point if point is not None else self.real2pix(self.mouse_real_pos)
        selected_unit = self.api.nearest_uid(self.mouse_real_pos, alive_only=False)[0]
        unit_pos = self.api.get_position(selected_unit)
        unit_pix_pos = self.real2pix(unit_pos)
        if math.dist(point, unit_pix_pos) < self.click_select_range:
            self.select_unit(selected_unit)
            Assets.play_sfx('ui', 'select',
                volume=Settings.get_volume('feedback'))
            chsize = minmax(50, 200, 200/self.upp)
            chsize = cc_int((chsize, chsize))
            self.api.add_visual_effect(VisualEffect.SPRITE, 60, {
                'uid': selected_unit,
                'fade': 120,
                'category': 'ui',
                'source': 'crosshair2',
                'size': chsize,
                'tint': (0, 0, 0),
            })

    def use_right_click(self, point=None):
        point = point if point is not None else self.real2pix(self.mouse_real_pos)
        return self.quickcast(self.ability_hotkeys.index(self.right_click_ability))

    # Control
    def select_unit(self, uid):
        self.selected_unit = uid

    def quickcast(self, key_index):
        ao = self.api.units[0].ability_order
        if key_index >= len(ao):
            return
        a = ao[key_index]
        if a is None:
            return
        self.use_ability(ao[key_index], self.mouse_real_pos)

    def use_ability(self, aid, target):
        r = self.api.units[0].use_ability(self.api, aid, target)
        if r is None:
            logger.warning(f'Ability {self.api.abilities[aid].__class__} failed to return a result!')
        if isinstance(r, FAIL_RESULT):
            if r in FAIL_SFX:
                Assets.play_sfx('ui', FAIL_SFX[r], replay=False,
                    volume=Settings.get_volume('feedback'))
        if r is not FAIL_RESULT.INACTIVE:
            self.api.add_visual_effect(VisualEffect.SPRITE, 15, {
                'point': self.mouse_real_pos,
                'fade': 30,
                'category': 'ui',
                'source': 'crosshair',
                'size': (40, 40),
            })
        return r

    def toggle_map_zoom(self):
        if self.__units_per_pixel == self.DEFAULT_UPP:
            upp_to_fit_axes = np.array(self.api.map_size) / self.size
            v = max(upp_to_fit_axes) / 2
            logger.debug(f'Fitting map size into widget size, ratio: ' \
                         f'{self.api.map_size}/{self.size} = {upp_to_fit_axes} upp. Using: {v}')
            self.set_zoom(v=v)
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

    def toggle_play(self, show_menu=True):
        logger.debug(f'GUI toggling play/pause')
        self.api.set_auto_tick()
        self.toggle_play_sounds()
        # Toggle menu
        if self.api.auto_tick:
            self.enc_menu.set_view(False)
        elif show_menu and not self.api.auto_tick:
            self.enc_menu.set_view(True)

    def toggle_play_sounds(self):
        logger.debug(f'Toggling theme music, autotick: {self.api.auto_tick}')
        if self.api.auto_tick is True:
            Assets.play_sfx('ui', 'play', volume=Settings.get_volume('ui'))
            logger.debug(f'Playing theme {self._theme_track}')
            self._theme_track.play(loop=True, replay=False, volume=Settings.get_volume('music'))
        else:
            Assets.play_sfx('ui', 'pause', volume=Settings.get_volume('ui'))
            logger.debug(f'Pausing theme {self._theme_track}')
            self._theme_track.pause()

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
        return self.upp > 2.5

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

    def collide_top_corners(self, pos):
        margin = 0.01
        return (pos[1] > self.size[1]*(1-margin)) and any([
            pos[0] > self.size[0]*(1-margin),
            pos[0] < self.size[0]*margin,
        ])

    @property
    def click_select_range(self):
        return sum(self.size) / 15

    @property
    def zoom_level(self):
        return 1 / self.__units_per_pixel


FAIL_SFX = {
    FAIL_RESULT.INACTIVE: 'pause',
    FAIL_RESULT.MISSING_COST: 'cost',
    FAIL_RESULT.MISSING_TARGET: 'target',
    FAIL_RESULT.OUT_OF_BOUNDS: 'range',
    FAIL_RESULT.OUT_OF_RANGE: 'range',
    FAIL_RESULT.ON_COOLDOWN: 'cooldown',
}
