from collections import namedtuple
import numpy as np
import nutil
from nutil.random import SEED
from nutil.kex import widgets
from nutil.vars import minmax, modify_color
from nutil.display import make_title
from nutil.time import ratecounter, RateCounter, humanize_ms
from gui import cc_int, center_position
from gui.common import SpriteLabel, SpriteTitleLabel, SLStack, STLStack
from gui.encounter import EncounterViewComponent
from data import TITLE
from data.assets import Assets
from engine.common import *


Box = namedtuple('Box', ['box', 'sprite', 'label'])

HUD_HEIGHT = 150
HUD_WIDTH = 500
HUDAUX_WIDTH = 500


class ControlOverlay(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='top', **kwargs)
        frame = self.add(widgets.BoxLayout())
        self.buttons = []
        for i, name in enumerate(self.enc.api.control_buttons):
            btn = frame.add(widgets.Button(text=name, on_release=lambda *a, x=i: self.enc.api.control_button_click(x)))
            btn.set_size(x=70)
            self.buttons.append(btn)
        self.label = frame.add(widgets.Label(halign='center', valign='middle'))
        self.label.set_size(x=150)
        frame.set_size(x=150+70*(i+1), y=30)

    def update(self):
        self.label.text = f'{TITLE} | {round(self.app.fps.rate)} FPS'
        self.label.text_size = self.label.size
        self.label.make_bg(self.app.fps_color)
        for i, name in enumerate(self.enc.api.control_buttons):
            self.buttons[i].text = name


class LogicLabel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.label = self.add(widgets.Label(valign='top', halign='right'))
        self.label.set_size(x=150, y=250)

    def update(self):
        self.label.text = self.enc.api.general_label_text
        self.label.text_size = self.label.size
        self.label.make_bg(self.enc.api.general_label_color)


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='bottom', **kwargs)
        grid = self.add(widgets.GridLayout(cols=4))
        grid.set_size(x=HUD_WIDTH, y=HUD_HEIGHT)
        self.boxes = [grid.add(SpriteLabel()) for _ in range(8)]
        grid.make_bg((0, 0, 0, 0.25))

    def update(self):
        sprite_labels = self.api.hud_sprite_labels()
        for i, sl in enumerate(sprite_labels):
            self.boxes[i].update(sl)


class HUDAux(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='bottom', **kwargs)
        grid = self.add(widgets.GridLayout(cols=4))
        grid.set_size(x=HUDAUX_WIDTH, y=HUD_HEIGHT)
        self.boxes = [grid.add(SpriteLabel()) for _ in range(8)]
        grid.make_bg((0, 0, 0, 0.25))
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        if self.enc.size[0] < (HUDAUX_WIDTH + HUD_WIDTH*2):
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

        frame = self.add(widgets.BoxLayout(orientation='vertical'))
        frame.set_size(x=300, y=600)
        frame.add(widgets.Widget()).set_size(y=30)
        self.panel = frame.add(widgets.BoxLayout(orientation='vertical'))
        self.panel.make_bg((0, 0, 0, 0.3))

        self.sprite_frame = self.panel.add(widgets.BoxLayout())
        self.sprite_source = None
        self.sprite = self.sprite_frame.add(widgets.Image(allow_stretch=True))
        self.sprite.set_size(y=125)

        self.name_label = self.panel.add(widgets.Label(valign='middle', halign='center'))
        self.name_label.set_size(y=50)

        bar_frame = self.panel.add(widgets.BoxLayout(orientation='vertical'))
        bar_values = self.api.agent_panel_bars()
        bar_count = len(bar_values)
        bar_frame.set_size(y=20*bar_count)
        self.bars = [bar_frame.add(widgets.Progress(bg_color=(0, 0, 0, 0))) for _ in range(bar_count)]

        bottom_frame = self.panel.add(widgets.BoxLayout())
        boxes_frame = bottom_frame.add(widgets.BoxLayout(orientation='vertical'))
        self.boxes = []
        for i in range(6):
            box = boxes_frame.add(SpriteLabel())
            self.boxes.append(box)

        self.label = bottom_frame.add(widgets.Label(valign='top'))

    def update(self):
        bar_values = self.api.agent_panel_bars()
        for i, pbar in enumerate(bar_values):
            self.bars[i].progress = pbar.value
            self.bars[i].fg_color = pbar.color
            self.bars[i].text = pbar.text

        self.name_label.text = self.api.agent_panel_name()

        sprite_source = self.api.agent_panel_sprite()
        if sprite_source != self.sprite_source:
            self.sprite.source = self.sprite_source = sprite_source

        sls = self.api.agent_panel_boxes()
        for i, sl in enumerate(sls):
            self.boxes[i].update(sl)

        self.label.text = self.api.agent_panel_label()
        self.label.text_size = self.label.size


class ModalBrowse(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.4)

    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch())
        self.frame = self.add(widgets.BoxLayout())
        self.frame.make_bg((0,0,0,1))
        self.main = self.frame.add(SpriteTitleLabel())
        self.main.set_size(x=350)
        self.stack = self.frame.add(SLStack(callback=self.enc.api.modal_click))
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.frame.set_size(x=max(900, self.size[0]*0.8), y=max(700, self.size[1]*0.8))

    def update(self):
        if not self.enc.api.show_modal_browse:
            if self.frame in self.children:
                self.remove_widget(self.frame)
                self.make_bg((0,0,0,0))
                self.consume_touch.enable = False
            return
        if self.frame not in self.children:
            self.add(self.frame)
            self.make_bg(self.active_bg)
            self.consume_touch.enable = True
        main = self.enc.api.modal_browse_main()
        self.main.update(main)
        sts = self.enc.api.modal_browse_sts()
        self.stack.update(sts)


class ModalGrid(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.4)

    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch())
        self.frame = self.add(widgets.BoxLayout())
        self.frame.make_bg((0,0,0,1))
        self.stack = self.frame.add(STLStack(callback=self.enc.api.modal_click))
        self.stack.cols = 4
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.frame.set_size(x=max(900, self.size[0]*0.8), y=max(700, self.size[1]*0.8))

    def update(self):
        if not self.enc.api.show_modal_grid:
            if self.frame in self.children:
                self.remove_widget(self.frame)
                self.make_bg((0,0,0,0))
                self.consume_touch.enable = False
            return
        if self.frame not in self.children:
            self.add(self.frame)
            self.make_bg(self.active_bg)
            self.consume_touch.enable = True
        stls = self.enc.api.modal_grid()
        self.stack.update(stls)


class Menu(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.6)

    def __init__(self, **kwargs):
        super().__init__(halign='center', valign='middle', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch(False))
        self.frame = widgets.BoxLayout(orientation='vertical')
        self.label = self.frame.add(widgets.Label(text='Paused')).set_size(hy=1.5)
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
        self.label.text = f'Paused\n{self.enc.api.menu_text}'


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.main_panel = self.add(widgets.BoxLayout())
        self.main_panel.set_size(x=1400, y=800)
        self.main_panel.make_bg(v=0, a=0.75)

        self.panels = [self.main_panel.add(widgets.Label(valign='top', halign='left')
            ) for _ in range(10)]
        for panel in self.panels:
            panel.set_size(x=0)

    def update(self):
        if not self.api.show_debug:
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
