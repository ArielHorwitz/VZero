
from pathlib import Path
import numpy as np
import nutil
from nutil import display as ndis
from nutil.time import humanize_ms, pingpong
from nutil.random import SEED
from nutil.vars import nsign, NP
from nutil.display import njoin
from nutil.kex import widgets
from logic.encounter.encounter import Encounter
from logic.mechanics.common import *
from gui.tileset import TileMap


AUDIO_DIR = Path.cwd() / 'assets' / 'audio'
SPRITE_DIR = Path.cwd() / 'assets' / 'graphics' / 'sprites'
SFX = {sname: widgets.Sound.load(
    str(AUDIO_DIR/'Lokif'/f'{sname}.wav'), volume=v) for sname, v in (
    ('adrenaline', 0.25),
    ('attack', 1),
    ('beam', 0.25),
    ('blink', 0.25),
    ('cost', 0.25),
    ('move', 0.5),
    ('ouch', 0.15),
    ('range', 0.5),
    ('stop', 0.25),
    ('target', 0.5),
    ('ting', 0.25),
    ('loot', 0.5),
    ('tada', 0.1),
)}
MUSIC_TRACKS = {sname: widgets.Sound.load(
    str(AUDIO_DIR/f'{sname}.wav'), volume=0.2) for sname in (
    'theme',
)}

ABILITY_META = {
    ABILITIES.ATTACK: ('q', 'sword-glowburn.png'),
    ABILITIES.BLINK: ('w', 'blink.png'),
    ABILITIES.BLOODLUST: ('e', 'sword-divine.png'),
    ABILITIES.BEAM: ('r', 'piracy.png'),
    ABILITIES.LOOT: ('a', 'crosshair.png'),
    ABILITIES.STOP: ('s', 'banner.png'),
    ABILITIES.LOOT: ('d', 'crosshair.png'),
    ABILITIES.LOOT: ('f', 'crosshair.png'),
    ABILITIES.VIAL: ('z', 'vial.png'),
    ABILITIES.SHARD: ('x', 'shard.png'),
    ABILITIES.MOONSTONE: ('c', 'moonstone.png'),
    ABILITIES.BRANCH: ('v', 'folphin.png'),
}

COLOR_CODES = [
    (0, 1, 0),
    (1, 0, 0),
    (0, 0, 1),
    (0, 1, 1),
    (1, 1, 0),
    (1, 0, 1),
    *(tuple(SEED.r for _ in range(3)) for i in range(50)),
    (1, 1, 1),
    (0, 0, 0),
]


class EncounterGUI(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._music_track = MUSIC_TRACKS['theme']
        self.app.hotkeys.register_dict({
            'new game': (f'^ n', lambda: self.new_encounter()),
            'toggle pause': (f' spacebar', lambda: self.toggle_play()),
            # debug
            'debug': (f'^+ d', lambda: self.debug()),
            'debug dmod': (f'^+ v', lambda: self.debug(dmod=True)),
            'normal tps': (f'^+ t', lambda: self.debug(tps=None)),
            'high tps': (f'^!+ t', lambda: self.debug(tps=920)),
            'single tick': (f'^ t', lambda: self.debug(tick=1)),
        })
        self.selected_unit = 0

        self.api = Encounter.new_encounter()
        if self.api.e.auto_tick is True:
            self._music_track.play()

        left_pane = self.add(widgets.BoxLayout(orientation='vertical'))
        self.info_panel = self.add(widgets.BoxLayout(orientation='vertical')).set_size(x=250)

        # MAP
        self.map_view = left_pane.add(MapView(self.api, unit_selection=self.select_unit))
        self.map_view.redraw()

        # HUD
        self.hud = left_pane.add(HUD(self.api)).set_size(y=150)

        # INFO PANEL
        with self.info_panel.canvas:
            self.info_pic = widgets.kvImage(allow_stretch=True, size=(150, 150))
        self.info_label = self.info_panel.add(widgets.Label())
        for s, c in [
            ('Pause', lambda *a: self.toggle_play()),
            ('Single tick', lambda *a: self.api.do_ticks()),
            ('Restart', lambda *a: nutil.restart_script()),
            ('Quit', lambda *a: quit()),
        ]:
            self.info_panel.add(widgets.Button(text=s, on_release=c)).set_size(y=30)

    def new_encounter(self):
        self.api = Encounter.new_encounter()
        self.map_view.api = self.hud.api = self.api

    def toggle_play(self, *a, **k):
        play = self.api.set_auto_tick()
        if play:
            self._music_track.play(loop=True, replay=False)
        else:
            self._music_track.pause()

    def update_info_panel(self):
        stats = self.api.get_stats(index=slice(None), stat=slice(None), value_name=slice(None))
        unit = self.api.units[self.selected_unit]
        bg_color = list(np.array(COLOR_CODES[unit.color_code]) / 3)
        self.info_panel.make_bg(color=bg_color, hsv=False)
        self.info_label.text = ndis.njoin([
            ndis.make_title('Debug', length=30),
            f'Time: {humanize_ms(self.api.elapsed_time_ms)} ({self.api.tick})',
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            # f'TPS: {self.api.e.tps.rate:.1f} ({self.api.e.tps.mean_elapsed_ms:.1f} ms)',
            f'Map size: {self.api.map_size}',
            f'Map zoom: x{self.map_view.zoom_level:.2f} ({1/self.map_view.zoom_level:.2f} u/p)',
            f'Monsters: {self.api.get_live_monster_count()}',
            ndis.make_title(f'{unit.name}', length=30),
            f'{self.api.pretty_stats(self.selected_unit)}',
        ])
        self.info_pic.pos=(
            self.info_panel.pos[0],
            self.info_panel.pos[1]+self.info_panel.size[1]-self.info_pic.size[1])
        self.info_pic.source = str(SPRITE_DIR/unit.SPRITE)

    def select_unit(self, index=0):
        self.selected_unit = index

    def frame_update(self):
        self.api.update()
        self.map_view.update()
        self.update_info_panel()
        self.hud.update()

    def debug(self, *a, **k):
        return self.api.debug(*a, **k)


class MapView(widgets.DrawCanvas):
    UNIT_SIZE = (30, 30)

    def __init__(self, api, unit_selection, **kwargs):
        super().__init__(**kwargs)
        self.app.hotkeys.register_dict({
            **{f'ability {a.name.lower()}': (
            f' {key}', lambda *args, a=a: self.use_ability(a, self.mouse_real_pos)
            ) for a, (key, icon) in ABILITY_META.items()},
            'toggle range': (f'! r', lambda: self.set_draw_range()),
            'zoom in': (f' =', lambda: self.zoom(d=1.15)),
            'zoom out': (f' -', lambda: self.zoom(d=-1.15)),
            })
        self.__tilemap_source = TileMap(['tiles1']).make_map(100, 100)
        self.__on_unit_selection = unit_selection
        self.__units_per_pixel = 0.6
        self.__default_bg_color = (0, 0.15, 0, 1)
        self.__cached_vfx = []
        self.__cached_move = None
        self.__draw_ranges = False
        self.bind(on_touch_down=self.do_mouse_down)
        self.bind(on_touch_move=self.check_mouse_move)
        self.sprites = []
        self.api = api

    # Drawing
    def redraw(self):
        self.canvas.clear()

        with self.canvas.before:
            # Tilemap
            self.tilemap = widgets.Image(
               source=self.__tilemap_source,
               size=cc_int(self.api.map_size / self.__units_per_pixel),
               allow_stretch=True,
           )

        self.unit_sprites = []
        self.range_circles = []
        self.hps = []
        with self.canvas:
            for uid, unit in enumerate(self.api.units):
                # Sprite details
                color = COLOR_CODES[unit.color_code]
                sprite_file = unit.SPRITE
                # Draw and cache sprites
                sprite = widgets.Image(
                    source=str(SPRITE_DIR/sprite_file),
                    # size=self.UNIT_SIZE,
                    pos=(-1_000_000, -1_000_000),
                    allow_stretch=True,
                )
                self.unit_sprites.append(sprite)

                widgets.kvColor(*color)
                self.range_circles.append(widgets.kvLine(width=2))

                self.hps.append(self.add(widgets.ProgressBar()))

            widgets.kvColor(1, 1, 1)
            ch_size = (3, 3)
            ch_pos = center_position(self.api.get_position(0), ch_size)
            self.move_crosshair = widgets.kvEllipse(pos=ch_pos, size=ch_size)

    def update(self):
        if self.__cached_move is not None:
            self.use_ability(ABILITIES.MOVE, self.__cached_move, supress_sfx=True)
            self.__cached_move = None
        player_pos = self.api.get_position(0)
        self.__player_pos = player_pos
        self.__anchor_offset = np.array(self.size) / 2

        # Tilemap
        self.tilemap.size = cc_int(np.array(self.api.map_size) / self.__units_per_pixel)
        self.tilemap.pos = cc_int(self.real2pix(np.zeros(2)))

        self._draw_units()
        self._draw_vfx()

    def _draw_units(self):
        ranges = self.api.get_stats(index=slice(None), stat=STAT.RANGE)
        hps = 100 * self.api.get_stats(index=slice(None), stat=STAT.HP) / self.api.get_stats(index=slice(None), stat=STAT.HP, value_name=VALUE.MAX_VALUE)
        all_positions = self.api.get_position()

        for uid, unit in enumerate(self.api.units):
            sprite = self.unit_sprites[uid]
            pos = self.real2pix(all_positions[uid])
            # sprite
            hitbox_diameter = max(35, round(1.8 * unit.HITBOX / self.__units_per_pixel))
            sprite.size = hitbox_diameter, hitbox_diameter
            sprite.pos = center_position(pos, sprite.size)

            # hp bar
            hp_ = self.hps[uid].value = hps[uid]
            if hp_ > 0 and self.__units_per_pixel < 1.5:
                self.hps[uid].set_size(x=hitbox_diameter*2, y=20 / self.__units_per_pixel)
                hp_pos = pos + (0, hitbox_diameter/2)
                self.hps[uid].pos = center_position(hp_pos, self.hps[uid].size)
            else:
                self.hps[uid].pos = OUT_OF_DRAW_ZONE

            # range circle
            if self.__draw_ranges:
                attack_range = ranges[uid] / self.__units_per_pixel
                self.range_circles[uid].circle = (*pos, attack_range)


        target_pos = self.api.get_stats(0, (STAT.POS_X, STAT.POS_Y), VALUE.TARGET_VALUE)
        self.move_crosshair.pos = center_position(self.real2pix(target_pos), self.move_crosshair.size)

    def _draw_vfx(self):
        for instruction in self.__cached_vfx:
            self.canvas.remove(instruction)
        self.__cached_vfx = []

        effects = self.api.get_visual_effects()

        for effect in effects:
            # Flash background
            if effect.eid is effect.BACKGROUND:
                with self.canvas:
                    self.__cached_vfx.append(widgets.kvColor(1, 0, 0, 0.15))
                    self.__cached_vfx.append(widgets.kvRectangle(pos=self.to_local(*self.pos), size=self.size))

            # Draw line
            if effect.eid is effect.LINE:
                width = 2
                if 'width' in effect.params:
                    width = effect.params['width']
                color_code = -1
                if 'color_code' in effect.params:
                    color_code = effect.params['color_code']
                points = (*self.real2pix(effect.params['p1']),
                          *self.real2pix(effect.params['p2']))
                with self.canvas:
                    self.__cached_vfx.append(widgets.kvColor(*COLOR_CODES[color_code]))
                    self.__cached_vfx.append(widgets.kvLine(points=points, width=width))

            # SFX
            if effect.eid is effect.SFX:
                if self.api.e.auto_tick:
                    SFX[effect.params['sfx']].play()

    # Utility
    def use_ability(self, *a, supress_sfx=False, **k):
        r = self.api.use_ability(*a, **k)
        if supress_sfx == False:
            if r is FAIL_RESULT.MISSING_COST:
                print('Missing cost')
                SFX['cost'].play()
            if r is FAIL_RESULT.MISSING_TARGET:
                print('Missing target')
                SFX['target'].play()
            if r is FAIL_RESULT.OUT_OF_BOUNDS:
                print('Out of bounds')
                SFX['range'].play()
            if r is FAIL_RESULT.OUT_OF_RANGE:
                print('Out of range')
                SFX['range'].play()
            if r in ABILITIES:
                name = r.name.lower()
                if name in SFX:
                    SFX[name].play()
        return r

    @property
    def draw_boundary_real(self):
        size = np.array(self.size)
        bl = np.zeros(2) - size / 2
        return self.pix2real(bl), self.pix2real(bl + (size * 2))

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
    def mouse_real_pos(self):
        local = self.to_local(*self.app.mouse_pos)
        real = self.pix2real(local)
        return real

    def check_mouse_move(self, w, m):
        if m.button == 'right':
            self.__cached_move = self.mouse_real_pos

    def do_mouse_down(self, w, m):
        if not self.collide_point(*m.pos):
            return
        real_pos = self.mouse_real_pos
        if m.button == 'right':
            self.use_ability(ABILITIES.MOVE, real_pos)
        if m.button == 'left':
            selected_unit = self.api.nearest_uid(real_pos, alive=False)[0]
            self.__on_unit_selection(selected_unit)

    @property
    def zoom_level(self):
        return 1 / self.__units_per_pixel

    # Config
    def set_draw_range(self, v=None):
        if v is None:
            v = not self.__draw_ranges
        self.__draw_ranges = v
        if not self.__draw_ranges:
            for r in self.range_circles:
                r.circle = (*OUT_OF_DRAW_ZONE, 1)

    def zoom(self, d):
        self.__units_per_pixel *= abs(d)**(-1*nsign(d))


class HUD(widgets.BoxLayout):
    def __init__(self, api, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self.api = api
        self.make_bg((0.8, 1, 0.2))

        stats = self.add(widgets.BoxLayout()).set_size(x=150)
        self.stats_label = stats.add(widgets.Label())

        bar = self.add(widgets.BoxLayout(orientation='vertical'))

        atkcd_bar = bar.add(widgets.BoxLayout()).set_size(y=15)
        self.atkcd_label = atkcd_bar.add(widgets.Label()).set_size(x=200)
        self.atkcd = atkcd_bar.add(widgets.ProgressBar())
        hp_bar = bar.add(widgets.BoxLayout()).set_size(y=30)
        self.hp_label = hp_bar.add(widgets.Label()).set_size(x=200)
        self.hp = hp_bar.add(widgets.ProgressBar())
        mana_bar = bar.add(widgets.BoxLayout()).set_size(y=30)
        self.mana_label = mana_bar.add(widgets.Label()).set_size(x=200)
        self.mana = mana_bar.add(widgets.ProgressBar())

        self.cooldown_filters = {a: {} for a in ABILITIES}
        ability_bar = bar.add(widgets.BoxLayout())
        for ai, (ability, (key, ico)) in enumerate(ABILITY_META.items()):
            panel = ability_bar.add(widgets.BoxLayout()).set_size(hx=0.1)
            panel.make_bg((1-0.2*ai, 1, 0.3))
            im = panel.add(widgets.Image(
                source=str(SPRITE_DIR/ico),
                allow_stretch=True,
            )).set_size(hx=0.5)
            details = panel.add(widgets.Label(text=njoin([
                f'<{key.upper()}> {ability.name.lower().capitalize()}',
            ])))
            with im.canvas.after:
                self.cooldown_filters[ability]['color'] = widgets.kvColor(0, 0, 0, 1)
                self.cooldown_filters[ability]['rect'] = widgets.kvRectangle(pos=self.pos, size=self.size)
            self.cooldown_filters[ability]['panel'] = panel

    def update(self):
        attack_speed = self.api.get_stats(0, STAT.ATTACK_SPEED)
        max_cooldown = self.api.attack_speed_to_cooldown(attack_speed)
        current_cooldown = max(0, self.api.get_cooldown(0, ABILITIES.ATTACK))
        v = 1 - (current_cooldown / max_cooldown)
        self.atkcd_label.text = f'Attack cooldown: {current_cooldown:.1f}'
        self.atkcd.value = 100 * v

        hp, hp_max, hp_delta = self.api.get_stats(0, STAT.HP, value_name=(VALUE.CURRENT, VALUE.MAX_VALUE, VALUE.DELTA))
        hp_delta_str = f'(+ {hp_delta:.2f})' if hp_delta > 0 else ''
        self.hp_label.text = f'HP: {hp:.2f} / {hp_max:.2f}{hp_delta_str}'
        self.hp.value = 100 * hp / hp_max

        mana, mana_max, mana_delta = self.api.get_stats(0, STAT.MANA, (VALUE.CURRENT, VALUE.MAX_VALUE, VALUE.DELTA))
        mana_delta_str = f'(+ {mana_delta:.2f})' if mana_delta > 0 else ''
        self.mana_label.text = f'Mana: {mana:.2f} / {mana_max:.2f}{mana_delta_str}'
        self.mana.value = 100 * mana / mana_max

        self.stats_label.text = self.api.pretty_stats(0, stats=(
            STAT.MOVE_SPEED, STAT.RANGE, STAT.DAMAGE, STAT.GOLD))

        cds = self.api.get_cooldown(0)
        for ability in ABILITY_META.keys():
            if cds[ability] > 0:
                self.cooldown_filters[ability]['color'].rgba = (0, 0, 0, 0.5)
            else:
                self.cooldown_filters[ability]['color'].rgba = (0, 0, 0, 0)
            self.cooldown_filters[ability]['rect'].pos = self.to_local(*self.cooldown_filters[ability]['panel'].pos)
            self.cooldown_filters[ability]['rect'].size = self.cooldown_filters[ability]['panel'].size


def center_position(pos, size):
    r = list(np.array(pos) - (np.array(size) / 2))
    assert len(r) == 2
    return cc_int(r)


def cc_int(pos):
    return int(pos[0]), int(pos[1])


OUT_OF_DRAW_ZONE = (-1_000_000, -1_000_000)
