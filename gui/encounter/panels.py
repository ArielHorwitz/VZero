from collections import namedtuple
import numpy as np
import nutil
from nutil.random import SEED
from nutil.kex import widgets
from nutil.vars import minmax, modify_color
from nutil.display import make_title
from nutil.time import ratecounter, RateCounter, humanize_ms
from gui import cc_int, center_position
from gui.common import SpriteLabel, STLStack
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from engine.common import *


Box = namedtuple('Box', ['box', 'sprite', 'label'])


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='bottom', **kwargs)
        grid = self.add(widgets.GridLayout(cols=4))
        grid.set_size(x=600, y=150)
        self.boxes = [grid.add(SpriteLabel()) for _ in range(8)]
        grid.make_bg((0, 0, 0, 0.25))

    def update(self):
        sprite_labels = self.api.hud_sprite_labels()
        for i, sl in enumerate(sprite_labels):
            self.boxes[i].update(sl)


class HUDAux(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='bottom', **kwargs)
        grid = self.add(widgets.GridLayout(cols=3))
        grid.set_size(x=450, y=150)
        self.boxes = [grid.add(SpriteLabel()) for _ in range(6)]
        grid.make_bg((0, 0, 0, 0.25))
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        if self.enc.size[0] < 1650:
            self.anchor_x = 'right'
        else:
            self.anchor_x = 'center'

    def update(self):
        sprite_labels = self.api.hud_aux_sprite_labels()
        for i, sl in enumerate(sprite_labels):
            self.boxes[i].update(sl)


class AgentViewer(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='top', **kwargs)
        self.last_selected = -1

        self.panel = self.add(widgets.BoxLayout(orientation='vertical'))
        self.panel.set_size(x=300, y=500)
        self.panel.make_bg((0, 0, 0, 0.3))

        self.name_label = self.panel.add(widgets.Label(valign='middle', halign='center'))
        self.name_label.set_size(y=50)

        bar_frame = self.panel.add(widgets.BoxLayout(orientation='vertical'))
        bar_values = self.api.agent_panel_bars()
        bar_count = len(bar_values)
        bar_frame.set_size(y=20*bar_count)
        self.bars = [bar_frame.add(widgets.Progress(bg_color=(0, 0, 0, 0))) for _ in range(bar_count)]

        self.sprite_frame = self.panel.add(widgets.BoxLayout())
        self.sprite_source = None
        self.sprite = self.sprite_frame.add(widgets.Image(allow_stretch=True))

        boxes_frame = self.panel.add(widgets.GridLayout(cols=3))
        boxes_frame.set_size(y=140)
        self.boxes = []
        for i in range(6):
            box = boxes_frame.add(SpriteLabel())
            box.set_size(y=70)
            self.boxes.append(box)

        self.label = self.panel.add(widgets.Label(valign='top'))

    def get_sprite_size(self, uid):
        h = minmax(30, 150, self.api.get_sprite_size(uid) / self.enc.upp)
        return cc_int((h, h))

    def update(self):
        # self.panel.pos = 20, self.size[1] - self.panel.size[1] - 20

        bar_values = self.api.agent_panel_bars()
        for i, pbar in enumerate(bar_values):
            self.bars[i].progress = pbar.value
            self.bars[i].fg_color = pbar.color
            self.bars[i].text = pbar.text

        self.name_label.text = self.api.agent_panel_name()

        sprite_source, sprite_size = self.api.agent_panel_sprite()
        sprite_pos = np.array(self.sprite_frame.pos) + (np.array(self.sprite_frame.size) / 2)
        self.sprite.pos = center_position(sprite_pos, sprite_size)
        if sprite_source != self.sprite_source:
            self.sprite.source = self.sprite_source = sprite_source
        self.sprite.set_size(*sprite_size)

        sls = self.api.agent_panel_boxes()
        for i, sl in enumerate(sls):
            self.boxes[i].update(sl)

        self.label.text = self.api.agent_panel_label()
        self.label.text_size = self.label.size


class Modal(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.4)

    def __init__(self, **kwargs):
        super().__init__(halign='center', valign='middle', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch())
        self.frame = self.add(STLStack(callback=self.enc.api.modal_click))
        self.frame.set_size(hx=0.5, hy=0.7)
        self.frame.make_bg((0,0,0,1))

    def update(self):
        if not self.enc.api.show_modal:
            if self.frame in self.children:
                self.remove_widget(self.frame)
                self.make_bg((0,0,0,0))
                self.consume_touch.enable = False
            return
        if self.frame not in self.children:
            self.add(self.frame)
            self.make_bg(self.active_bg)
            self.consume_touch.enable = True
        stls = self.enc.api.modal_stls()
        self.frame.update(stls)


class Menu(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.6)

    def __init__(self, **kwargs):
        super().__init__(halign='center', valign='middle', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch(False))
        self.frame = widgets.BoxLayout(orientation='vertical')
        self.frame.add(widgets.Label(text='Paused')).set_size(hy=1.5)
        for t, c in (
            ('Resume', lambda *a: self.enc.api.user_hotkey('toggle_play', (0, 0))),
            ('Restart', lambda *a: nutil.restart_script()),
            ('Quit', lambda *a: quit()),
        ):
            self.frame.add(widgets.Button(text=t, on_release=c))
        self.frame.set_size(x=200, y=200)
        self.frame.make_bg((0,0,0,1))

    def consume_touch(self, w, m):
        return True

    def update(self):
        if not self.enc.api.show_menu:
            if self.frame in self.children:
                self.remove_widget(self.frame)
                self.make_bg((0,0,0,0))
                self.consume_touch.enable = False
            return
        if self.frame not in self.children:
            self.add(self.frame)
            self.make_bg(self.active_bg)
            self.consume_touch.enable = True


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.main_panel = self.add(widgets.BoxLayout())
        self.main_panel.set_size(x=1400, y=800)
        self.main_panel.make_bg(v=0, a=0.25)

        self.panels = [self.main_panel.add(widgets.Label(valign='top', halign='left')
            ) for _ in range(10)]
        for panel in self.panels:
            panel.set_size(x=0)

    def update(self):
        if not self.api.dev_mode:
            self.pos = self.enc.OUT_OF_DRAW_ZONE
            return
        self.pos = 0, 0

        perf_strs = [
            make_title('GUI Performance', length=30),
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            f'View size: {list(round(_) for _ in self.enc.view_size)}',
            f'Map zoom: x{self.enc.zoom_level:.2f} ({self.enc.upp:.2f} u/p)',
            f'Units: {len(self.api.units)} (drawing: {self.enc.overlays["sprites"].drawn_count})',
            f'vfx count: {len(self.api.get_visual_effects())}',
        ]
        for tname, timer in self.enc.timers.items():
            if isinstance(timer, RateCounter):
                perf_strs.append(f'- {tname}: {timer.mean_elapsed_ms:.3f} ms')
        text0 = '\n'.join(perf_strs)
        texts = [text0, *self.api.debug_panel_labels()]
        for i, text in enumerate(texts):
            panel = self.panels[-i-1]
            panel.text = text
            w = int(self.main_panel.size[0]/len(texts))
            panel.text_size = w, self.main_panel.size[1]
            panel.size_hint = 1, 1
            panel.set_size(x=w)
