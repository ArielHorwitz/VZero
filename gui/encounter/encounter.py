
import numpy as np
from nutil import display as ndis
from nutil.time import humanize_ms
from nutil.random import SEED
from nutil.gui.kex import widgets
from logic.encounter.encounter import Encounter, EncounterAPI, ABILITIES
from logic.encounter.stats import StatNames as STAT
from logic.encounter.stats import ValueNames as VALUES


COLOR_CODES = [
    (0, 1, 0),
    (1, 0, 0),
    (0, 0, 1),
    (0, 1, 1),
    (1, 1, 0),
    (1, 0, 1),
    *(tuple(SEED.r for _ in range(3)) for i in range(50))
]

ABILITY_HOTKEYS = {
    'a': ABILITIES.MOVE,
    's': ABILITIES.STOP,
    'q': ABILITIES.ATTACK,
    'w': ABILITIES.BLAST,
    'e': ABILITIES.NUKE,
    'r': ABILITIES.TELEPORT,
}


class EncounterGUI(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app.hotkeys.register_dict({
            **{f'ability {a.name.lower()}': (
                f' {key}', lambda *args, a=a: self.use_ability(a)
            ) for key, a in ABILITY_HOTKEYS.items()},
            'debug action': (f'^+ d', lambda: self.api.debug()),
            'toggle auto tick': (f'^+ t', lambda: self.api.debug(auto_tick=None)),
            'single tick': (f'^ t', lambda: self.api.debug(tick=1)),
        })

        self.api = Encounter().api

        self.map_view = self.add(MapView(self.api))
        self.map_view.redraw()
        side_pane = self.add(widgets.BoxLayout(orientation='vertical')).set_size(hx=0.5)
        self.info_panel = side_pane.add(widgets.Label())
        self.hud = side_pane.add(HUD(self.api))

    def use_ability(self, ability, target=None):
        if target is None:
            target = self.app.mouse_pos
        self.api.use_ability(ABILITIES.MOVE, ability, target)

    def update_info_panel(self):
        self.info_panel.text = ndis.njoin([
            ndis.make_title('Debug', length=30),
            f'Time: {humanize_ms(self.api.elapsed_time_ms())} ({self.api.tick})',
        ])

    def select_unit(self, index=0):
        self.selected_unit = index
        stats = self.encounter.unit_stats[index]
        unit = self.encounter.units[index]
        color = list(np.array(COLOR_CODES[unit.allegience])/3)
        self.info_panel.make_bg(color=color, hsv=False)

    def frame_update(self):
        self.api.update()
        self.map_view.update()
        self.update_info_panel()
        self.hud.update()


class MapView(widgets.DrawCanvas):
    UNIT_SIZE = 10

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.bind(on_touch_down=self.do_mouse_down)
        self.sprites = []
        self.api = api

    def do_mouse_down(self, w, m):
        if not self.collide_point(*m.pos):
            return
        if m.button == 'right':
            self.parent.use_ability(ABILITIES.MOVE, m.pos)
        if m.button == 'left':
            pass

    def redraw(self):
        self.canvas.clear()
        self.make_bg((0.4, 1, 0.2))

        self.unit_sprites = []
        self.range_circles = []
        self.hps = []
        with self.canvas:
            for uid, unit in enumerate(self.api.units):
                # sprite details
                ustats = self.api.get_unit_stats(uid)
                sprite_size = (self.UNIT_SIZE, self.UNIT_SIZE)
                pos = (ustats[STAT.POS_X], ustats[STAT.POS_Y])
                sprite_pos = center_position(pos, sprite_size)
                color = COLOR_CODES[unit.color_code]
                # draw and add sprites
                widgets.kvColor(*color)
                sprite = widgets.kvEllipse(pos=sprite_pos, size=sprite_size)
                self.unit_sprites.append(sprite)
                self.range_circles.append(widgets.kvLine(circle=(*pos, 50)))
                self.hps.append(self.add(widgets.ProgressBar()).set_size(x=50, y=10))
                if uid == 0:
                    widgets.kvColor(1, 1, 1)
                    ch_size = (3, 3)
                    ch_pos = center_position(pos, ch_size)
                    self.move_crosshair = widgets.kvEllipse(pos=ch_pos, size=ch_size)

    def update(self):
        hps = self.api.get_stats_table()[:, STAT.HP, VALUES.VALUE]
        ranges = self.api.get_stats_table()[:, STAT.RANGE, VALUES.VALUE]
        for uid, sprite in enumerate(self.unit_sprites):
            # sprite
            pos = self.api.get_position(uid)
            sprite.pos = center_position(pos, sprite.size)

            # hp bar
            self.hps[uid].value = hps[uid]
            self.hps[uid].pos = int(pos[0]-25), int(pos[1]+5)

            # range circle
            self.range_circles[uid].circle = (*pos, ranges[uid])

        target_pos = (
            self.api.get_stat(0, STAT.POS_X, VALUES.TARGET_VALUE),
            self.api.get_stat(0, STAT.POS_Y, VALUES.TARGET_VALUE)
            )
        self.move_crosshair.pos = center_position(target_pos, self.move_crosshair.size)


class HUD(widgets.BoxLayout):
    def __init__(self, api, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.api = api
        self.label = self.add(widgets.Label())
        self.hp = self.add(widgets.ProgressBar())

    def update(self):
        hp = self.api.get_stat(0, STAT.HP)
        self.hp.value = hp
        self.label.text = ndis.njoin([
            ndis.make_title(f'Player stats:', length=30),
            f'{self.api.pretty_stats(0)}',
        ])


def center_position(pos, size):
    r = list(np.array(pos) - (np.array(size) / 2))
    assert len(r) == 2
    return r
