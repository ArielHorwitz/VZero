import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import numpy as np
import nutil
from nutil.random import SEED
from nutil.kex import widgets
from nutil.vars import minmax, modify_color
from nutil.display import make_title
from nutil.time import ratecounter, RateCounter, humanize_ms
from gui import cc_int, center_position
from gui.common import SpriteLabel, CenteredSpriteBox, SpriteTitleLabel, SpriteBox, Stack, Modal
from gui.encounter import EncounterViewComponent
from data import TITLE
from data.assets import Assets
from engine.common import *


Box = namedtuple('Box', ['box', 'sprite', 'label'])

BAR_HEIGHT = 30
HUD_HEIGHT = 100
HUD_WIDTH = 300
MIDDLE_HUD = 200
BAR_WIDTH = HUD_WIDTH * 2 + MIDDLE_HUD
TOTAL_HUD_HEIGHT = HUD_PORTRAIT = HUD_HEIGHT + BAR_HEIGHT
TOTAL_HUD_WIDTH = BAR_WIDTH + HUD_PORTRAIT * 2


class ControlOverlay(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='top', **kwargs)
        frame = self.add(widgets.BoxLayout())
        self.buttons = []
        for i, name in enumerate(self.api.control_buttons):
            btn = frame.add(widgets.Button(text=name, on_release=lambda *a, x=i: self.api.control_button_click(x)))
            btn.set_size(x=70)
            self.buttons.append(btn)
        self.label = frame.add(widgets.Label(halign='center', valign='middle'))
        self.label.set_size(x=150)
        frame.set_size(x=150+70*(i+1), y=30)

    def update(self):
        self.label.text = f'{TITLE} | {round(self.app.fps.rate)} FPS'
        self.label.text_size = self.label.size
        self.label.make_bg(self.app.fps_color)
        for i, name in enumerate(self.api.control_buttons):
            self.buttons[i].text = name


class LogicLabel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.label = self.add(widgets.Label(valign='top', halign='right'))
        self.label.set_size(x=150, y=250)

    def update(self):
        self.label.text = self.api.general_label_text
        self.label.text_size = self.label.size
        self.label.make_bg(self.api.general_label_color)


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='bottom', **kwargs)
        ct1 = self.add(widgets.ConsumeTouch(consume_keys=False))
        ct2 = self.add(widgets.ConsumeTouch(consume_keys=False))

        main_frame = self.add(widgets.BoxLayout())
        main_frame.set_size(x=TOTAL_HUD_WIDTH, y=TOTAL_HUD_HEIGHT)

        self.portrait = main_frame.add(widgets.Image(allow_stretch=True)).set_size(x=HUD_PORTRAIT, y=HUD_PORTRAIT)
        self.portrait.make_bg((0,0,0,0.5))
        center_frame = main_frame.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.add(widgets.Widget()).set_size(x=HUD_PORTRAIT, y=HUD_PORTRAIT)

        ct1.widget = self.portrait
        ct2.widget = center_frame

        self.status_panel = center_frame.add(Stack(wtype=CenteredSpriteBox, x=50, y=50))
        self.status_panel.make_bg((0,0,0,0))
        self.status_panel.set_size(y=50)

        bars = center_frame.add(widgets.BoxLayout(orientation='vertical'))
        bars.set_size(x=BAR_WIDTH, y=BAR_HEIGHT)
        self.bars = [bars.add(widgets.Progress()) for _ in range(len(self.api.hud_bars()))]

        main_panel = center_frame.add(widgets.BoxLayout())
        main_panel.set_size(y=HUD_HEIGHT)
        self.left_hud = main_panel.add(Stack(
            wtype=CenteredSpriteBox,
            callback=lambda i, b: self.click('left', i, b),
            x=HUD_WIDTH/4, y=HUD_HEIGHT/2))
        self.left_hud._bg_color.rgba = (1,1,1,1)
        self.left_hud._bg.source = Assets.get_sprite('ui', 'hud1')
        self.left_hud.set_size(HUD_WIDTH, HUD_HEIGHT)

        self.middle_hud = main_panel.add(Stack(
            wtype=SpriteLabel,
            callback=lambda i, b: self.click('middle', i, b),
            x=MIDDLE_HUD/3, y=HUD_HEIGHT/2))
        self.middle_hud._bg_color.rgba = (0.2,0.2,0.2,1)
        self.middle_hud.set_size(x=MIDDLE_HUD)

        self.right_hud = main_panel.add(Stack(
            wtype=CenteredSpriteBox,
            callback=lambda i, b: self.click('right', i, b),
            x=HUD_WIDTH/4, y=HUD_HEIGHT/2))
        self.right_hud._bg_color.rgba = (1,1,1,1)
        self.right_hud._bg.source = Assets.get_sprite('ui', 'hud2')
        self.right_hud.set_size(HUD_WIDTH, HUD_HEIGHT)

        self.bind(pos=self.reposition, size=self.reposition)

    def click(self, hud, index, button):
        stl = self.api.hud_click(hud, index, button)
        if stl is not None:
            self.enc.tooltip.activate(self.app.mouse_pos, stl)

    def reposition(self, *a):
        self.anchor_x = 'left' if self.enc.size[0] < TOTAL_HUD_WIDTH else 'center'

    def update(self):
        self.portrait.source = self.api.hud_portrait()
        self.status_panel.update(self.api.hud_statuses())
        self.left_hud.update(self.api.hud_left())
        self.middle_hud.update(self.api.hud_middle())
        self.right_hud.update(self.api.hud_right())
        bars = self.api.hud_bars()
        for i, pb in enumerate(bars):
            self.bars[i].progress = pb.value
            self.bars[i].text = pb.text
            self.bars[i].fg_color = pb.color


class ModalBrowseOld(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.4)

    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='center', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch())
        self.frame = self.add(widgets.BoxLayout())
        self.frame.make_bg((0,0,0,1))
        self.main = self.frame.add(SpriteTitleLabel())
        self.main.set_size(x=350)
        self.stack = self.frame.add(Stack(
            wtype=SpriteBox, x=50, y=50,
            callback=self.api.modal_click))
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.frame.set_size(x=700, y=500)

    def update(self):
        if not self.api.show_modal_browse:
            if self.frame in self.children:
                self.remove_widget(self.frame)
                self.make_bg((0,0,0,0))
                self.consume_touch.enable = False
            return
        if self.frame not in self.children:
            self.add(self.frame)
            self.make_bg(self.active_bg)
            self.consume_touch.enable = False
        main = self.api.modal_browse_main()
        self.main.update(main)
        sts = self.api.modal_browse_sts()
        self.stack.update(sts)


class ModalBrowse(Modal, EncounterViewComponent):
    active_bg = (0,0,0,0.4)

    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='center', **kwargs)
        self.frame = widgets.BoxLayout()
        self.frame.set_size(x=700, y=500)
        self.frame.make_bg((0,0,0,1))
        self.main = self.frame.add(SpriteTitleLabel())
        self.main.set_size(x=350)
        self.stack = self.frame.add(Stack(
            wtype=SpriteBox, x=50, y=50,
            callback=self.api.browse_click))
        self.set_frame(self.frame)

    def update(self):
        if self.api.check_flag('browse_toggle'):
            if self.activated:
                self.deactivate()
            else:
                self.activate()
        if self.api.check_flag('browse_dismiss'):
            self.deactivate()
        if self.api.check_flag('browse'):
            self.activate()
        if not self.activated:
            return
        main = self.api.browse_main()
        self.main.update(main)
        sts = self.api.browse_elements()
        self.stack.update(sts)


class Menu(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.6)

    def __init__(self, **kwargs):
        super().__init__(halign='center', valign='middle', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch(False))
        self.frame = widgets.BoxLayout(orientation='vertical')
        self.label = self.frame.add(widgets.Label(text='Paused')).set_size(hy=1.5)
        for t, c in (
            ('Resume', lambda *a: self.api.user_hotkey('toggle_play', (0, 0))),
            ('Restart', lambda *a: nutil.restart_script()),
            ('Quit', lambda *a: quit()),
        ):
            self.frame.add(widgets.Button(text=t, on_release=c))
        self.frame.set_size(x=200, y=200)
        self.frame.make_bg((0,0,0,1))

    def consume_touch(self, w, m):
        return True

    def update(self):
        if self.api.check_flag('menu_dismiss'):
            if self.frame in self.children:
                self.remove_widget(self.frame)
                self.make_bg((0,0,0,0))
                self.consume_touch.enable = False
            return
        if self.api.check_flag('menu'):
            if self.frame not in self.children:
                self.add(self.frame)
                self.make_bg(self.active_bg)
                self.consume_touch.enable = True
        if self.frame not in self.children:
            return
        self.label.text = f'Paused\n{self.api.menu_text}'


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.main_panel = self.add(widgets.BoxLayout())
        # self.main_panel.set_size(x=1400, y=800)
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
