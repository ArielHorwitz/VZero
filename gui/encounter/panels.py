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
from data.settings import Settings
from engine.common import *


Box = namedtuple('Box', ['box', 'sprite', 'label'])

AUTO_TOOLTIP = Settings.get_setting('auto_tooltip', 'UI')
HUD_SCALING = Settings.get_setting('hud_scale', 'UI')
HUD_WIDTH = 300
MIDDLE_HUD = 230
HUD_HEIGHT = 120 * HUD_SCALING
BAR_HEIGHT = 64 * (HUD_SCALING / 2)
BAR_WIDTH = HUD_WIDTH * 2 + MIDDLE_HUD
TOTAL_HUD_HEIGHT = HUD_PORTRAIT = HUD_HEIGHT + BAR_HEIGHT
TOTAL_HUD_WIDTH = BAR_WIDTH + HUD_PORTRAIT

RESUME_TEXT = 'Resume'
RESTART_TEXT = 'Restart'
RESTART_CONFIRM_TEXT = 'We can do better!'
LEAVE_TEXT = 'Leave'
LEAVE_CONFIRM_TEXT = 'Leave to menu?'
QUIT_TEXT = 'Quit'
QUIT_CONFIRM_TEXT = 'Quit to desktop?'


class LogicLabel(widgets.AnchorLayout, EncounterViewComponent):
    overlay_height = 50
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='top', **kwargs)
        self.main_frame = main_frame = self.add(widgets.BoxLayout())
        main_frame.make_bg((1,1,1,1))
        main_frame._bg.source = Assets.get_sprite('ui', 'panel-top')
        main_frame.set_size(y=self.overlay_height)

        self.left_label = main_frame.add(widgets.Label(halign='center', valign='top', outline_width=2))

        self.general_label1 = main_frame.add(widgets.Label(halign='center', valign='top', outline_width=2))
        self.general_label2 = main_frame.add(widgets.Label(halign='center', valign='top', outline_width=2))
        self.general_label3 = main_frame.add(widgets.Label(halign='center', valign='top', outline_width=2))

        a = main_frame.add(widgets.AnchorLayout(anchor_y='top'))
        self.debug_label = a.add(widgets.Label(halign='center', valign='top', outline_width=2))
        self.debug_label.set_size(x=160, y=25)
        self.debug_label.make_bg((0,0,0,0))
        self.debug_label._bg.source = Assets.get_sprite('ui', 'mask-4x1')

    def update(self):
        self.main_frame._bg_color.rgba = self.api.top_panel_color

        labels = self.api.top_panel_labels()
        self.left_label.text = labels[0]
        self.left_label.text_size = self.left_label.size

        self.general_label1.text = labels[1]
        self.general_label1.text_size = self.general_label1.size
        self.general_label2.text = labels[2]
        self.general_label2.text_size = self.general_label2.size
        self.general_label3.text = labels[3]
        self.general_label3.text_size = self.general_label3.size

        self.debug_label.text = f'{TITLE} | {round(self.app.fps.rate)} FPS'
        self.debug_label.text_size = self.debug_label.size
        self.debug_label.make_bg(self.app.fps_color)


class Decoration(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for side in ('left', 'right'):
            anchor = self.add(widgets.AnchorLayout(anchor_x=side, anchor_y='center'))
            frame = anchor.add(widgets.BoxLayout())
            frame.make_bg((1,1,1,Settings.get_setting('decorations', 'UI')))
            frame._bg.source = Assets.get_sprite('ui', f'side-{side}')
            frame.set_size(x=40)
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.pos = self.enc.pos
        self.size = self.enc.size


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    overlay_height = TOTAL_HUD_HEIGHT
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='bottom', **kwargs)
        ct1 = self.add(widgets.ConsumeTouch(consume_keys=False))
        ct2 = self.add(widgets.ConsumeTouch(consume_keys=False))

        self.main_frame = main_frame = self.add(widgets.BoxLayout())
        main_frame.set_size(x=TOTAL_HUD_WIDTH, y=self.overlay_height)

        self.portrait_frame = portrait_frame = main_frame.add(widgets.BoxLayout(orientation='vertical'))
        portrait_frame.set_size(x=HUD_PORTRAIT, y=HUD_PORTRAIT)
        portrait_frame.make_bg((1,1,1,1))
        portrait_frame._bg.source = Assets.get_sprite('ui', 'portrait')
        portrait_frame.bind(on_touch_down=self.portrait_click)
        self.name_label = portrait_frame.add(widgets.Label(halign='center', valign='middle'))
        self.portrait = portrait_frame.add(widgets.Image(allow_stretch=True, keep_ratio=True))
        self.name_label.set_size(y=25)
        self.name_label.text_size = self.name_label.size
        center_frame = main_frame.add(widgets.BoxLayout(orientation='vertical'))

        ct1.widget = self.portrait
        ct2.widget = center_frame

        a = center_frame.add(widgets.AnchorLayout(anchor_x='left'))
        a.set_size(y=50)
        self.status_panel = a.add(Stack(
            wtype=CenteredSpriteBox,
            callback=lambda i, b: self.click('status', i, b),
            x=50, y=50))
        self.status_panel.make_bg((0,0,0,0))

        bars = center_frame.add(widgets.BoxLayout(orientation='vertical'))
        bars.set_size(x=BAR_WIDTH, y=BAR_HEIGHT)
        s = Assets.get_sprite('ui', 'stat-bar')
        self.bars = [bars.add(widgets.Progress(source=s)) for _ in range(len(self.api.hud_bars()))]

        main_panel = center_frame.add(widgets.BoxLayout())
        main_panel.set_size(y=HUD_HEIGHT)

        padding = 0.95, 0.95
        left_panel = main_panel.add(widgets.AnchorLayout())
        left_panel.set_size(HUD_WIDTH, HUD_HEIGHT).make_bg((1,1,1,1))
        left_panel._bg.source = Assets.get_sprite('ui', 'hud-left')
        self.left_hud = left_panel.add(Stack(
            wtype=lambda *a, **k: CenteredSpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui', 'sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui', 'sprite-box'),
                **k),
            callback=lambda i, b: self.click('left', i, b),
            drag_drop_callback=lambda *a: self.api.hud_drag_drop('left', *a),
            x=HUD_WIDTH*padding[0]/4, y=HUD_HEIGHT*padding[1]/2))
        self.left_hud._bg_color.rgba = (0,0,0,0)
        self.left_hud.set_size(hx=padding[0], hy=padding[1])

        middle_panel = main_panel.add(widgets.BoxLayout(orientation='vertical'))
        middle_panel.set_size(x=MIDDLE_HUD).make_bg((1,1,1,1))
        middle_panel._bg.source = Assets.get_sprite('ui', 'hud-middle')
        middle_hud_anchor = middle_panel.add(widgets.AnchorLayout())
        middle_hud_size = MIDDLE_HUD*padding[0], HUD_HEIGHT*padding[1]*0.75
        self.middle_hud = middle_hud_anchor.add(Stack(
            wtype=SpriteLabel, callback=lambda i, b: self.click('middle', i, b),
            x=middle_hud_size[0]/3, y=middle_hud_size[1]/3))
        self.middle_hud._bg_color.rgba = (0,0,0,0)
        self.middle_hud.set_size(x=middle_hud_size[0], y=middle_hud_size[1])
        self.middle_label = middle_panel.add(widgets.Label(halign='center', valign='middle'))
        self.middle_label.make_bg((0,0,0,0.3))
        self.middle_label.set_size(y=HUD_HEIGHT-middle_hud_size[1])
        self.middle_label._bg.source = Assets.get_sprite('ui', 'mask-4x1')

        right_panel = main_panel.add(widgets.AnchorLayout())
        right_panel.set_size(HUD_WIDTH, HUD_HEIGHT).make_bg((1,1,1,1))
        right_panel._bg.source = Assets.get_sprite('ui', 'hud-right')
        self.right_hud = right_panel.add(Stack(
            wtype=lambda *a, **k: CenteredSpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui', 'sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui', 'sprite-box'),
                **k),
            callback=lambda i, b: self.click('right', i, b),
            drag_drop_callback=lambda *a: self.api.hud_drag_drop('right', *a),
            x=HUD_WIDTH*padding[0]/4, y=HUD_HEIGHT*padding[1]/2))
        self.right_hud._bg_color.rgba = (0,0,0,0)
        self.right_hud.set_size(hx=padding[0], hy=padding[1])

        self.bind(pos=self.reposition, size=self.reposition)

    def portrait_click(self, w, m):
        if not self.portrait_frame.collide_point(*m.pos):
            return
        stl = self.api.hud_portrait_click()
        if stl is not None:
            self.enc.tooltip.activate(self.app.mouse_pos, stl)

    def click(self, hud, index, button):
        stl = self.api.hud_click(hud, index, button)
        if stl is not None:
            self.enc.tooltip.activate(self.app.mouse_pos, stl)

    def reposition(self, *a):
        self.anchor_x = 'left' if self.enc.size[0] < TOTAL_HUD_WIDTH else 'center'
        self.name_label.text_size = self.name_label.size

    def update(self):
        if not self.api.show_hud:
            self.set_auto_hover(False)
            if self.main_frame in self.children:
                self.remove_widget(self.main_frame)
            return
        else:
            if self.main_frame not in self.children:
                self.add(self.main_frame)
        self.set_auto_hover(self.api.detailed_info_mode if self.api.show_hud else False)
        self.portrait.source = self.api.hud_portrait()
        self.name_label.text = self.api.hud_name()
        self.status_panel.update(self.api.hud_statuses())
        self.status_panel.set_size(x=len(self.status_panel.boxes)*50)
        self.left_hud.update(self.api.hud_left())
        self.middle_label.text = self.api.hud_middle_label()
        self.middle_label.text_size = self.middle_label.size
        self.middle_hud.update(self.api.hud_middle())
        self.right_hud.update(self.api.hud_right())
        bars = self.api.hud_bars()
        for i, pb in enumerate(bars):
            self.bars[i].progress = pb.value
            self.bars[i].text = pb.text
            self.bars[i].fg_color = pb.color

    def set_auto_hover(self, set_as=None):
        if not AUTO_TOOLTIP:
            return
        set_as = self.api.detailed_info_mode if set_as is None else set_as
        self.middle_hud.consider_hover = set_as
        self.right_hud.consider_hover = set_as
        self.left_hud.consider_hover = set_as
        self.status_panel.consider_hover = set_as


class ModalBrowse(Modal, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='top', padding=150, **kwargs)
        item_box_size = 50
        main_width = 250
        main_height = 400
        stack_size = item_box_size * 10
        self.frame = widgets.BoxLayout()
        self.main = self.frame.add(SpriteTitleLabel())
        self.main.set_size(x=main_width)
        self.stack = self.frame.add(Stack(
            wtype=lambda *a, **k: SpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui', 'sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui', 'sprite-box'),
                valign='bottom', **k),
            x=item_box_size, y=item_box_size,
            callback=self.click))
        self.stack.set_size(stack_size, main_height)
        self.stack.make_bg((0,0,0,0.5))

        self.frame.set_size(x=main_width+stack_size, y=main_height)
        self.set_frame(self.frame)

    def click(self, index, button):
        stl = self.api.browse_click(index, button)
        if stl is not None:
            self.enc.tooltip.activate(self.app.mouse_pos, stl)

    def update(self):
        if self.api.check_flag('browse_toggle'):
            if self.activated:
                self.deactivate()
                self.enc.tooltip.deactivate()
            else:
                self.activate()
        if self.api.check_flag('browse_dismiss'):
            self.deactivate()
            self.enc.tooltip.deactivate()
        if self.api.check_flag('browse'):
            self.activate()
        if not self.activated:
            self.stack.consider_hover = False
            return
        self.main.update(self.api.browse_main())
        self.stack.update(self.api.browse_elements())
        self.stack.consider_hover = self.api.detailed_info_mode if AUTO_TOOLTIP else False


class ViewFade(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update(self):
        self.make_bg(self.api.view_fade)


class Menu(widgets.AnchorLayout, EncounterViewComponent):
    active_bg = (0,0,0,0.6)

    def __init__(self, **kwargs):
        super().__init__(halign='center', valign='middle', **kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch(False))
        self.margin = 0.9, 0.9
        self.frame = widgets.BoxLayout(orientation='vertical')
        self.frame.set_size(x=200, y=250)
        self.frame.make_bg((0, 0, 0, 1))
        self.frame._bg.source = Assets.get_sprite('ui', 'mask-1x2')

        self.label = self.frame.add(widgets.Label(text='', halign='center', valign='middle', markup=True, line_height=1.2))
        self.label.set_size(y=100)

        self.frame.add(widgets.Button(text=RESUME_TEXT, on_release=lambda *a: self.api.user_hotkey('toggle_menu', None)))
        self.restart_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_restart()))
        self.leave_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_leave()))
        self.quit_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_quit()))

        self.confirm_restart = False
        self.confirm_leave = False
        self.confirm_quit = False
        self.unconfirm()

    def unconfirm(self):
        self.confirm_restart = False
        self.restart_btn.text = RESTART_TEXT
        self.confirm_leave = False
        self.leave_btn.text = LEAVE_TEXT
        self.confirm_quit = False
        self.quit_btn.text = QUIT_TEXT

    def click_restart(self):
        if self.confirm_restart:
            self.app.game.restart_encounter()
        else:
            self.unconfirm()
            self.confirm_restart = True
            self.restart_btn.text = RESTART_CONFIRM_TEXT

    def click_leave(self):
        if self.confirm_leave:
            self.app.game.leave_encounter()
        else:
            self.unconfirm()
            self.confirm_leave = True
            self.leave_btn.text = LEAVE_CONFIRM_TEXT

    def click_quit(self):
        if self.confirm_quit:
            self.app.stop()
        else:
            self.unconfirm()
            self.confirm_quit = True
            self.quit_btn.text = QUIT_CONFIRM_TEXT

    def consume_touch(self, w, m):
        return True

    def update(self):
        if self.api.check_flag('menu_dismiss'):
            if self.frame in self.children:
                self.unconfirm()
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
        self.label.text = self.api.menu_text


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='right', anchor_y='top', **kwargs)
        self.main_panel = self.add(widgets.BoxLayout())
        # self.main_panel.set_size(x=1400, y=800)
        self.main_panel.make_bg(v=0, a=0.75)

        self.panels = [self.main_panel.add(widgets.Label(valign='top', halign='left', markup=True)
            ) for _ in range(10)]
        for panel in self.panels:
            panel.set_size(x=0)

    def update(self):
        if not self.api.show_debug:
            self.pos = self.enc.OUT_OF_DRAW_ZONE
            return
        self.pos = 0, 0
        bold = {'draw/idle', 'frame_total', 'graphics_total', 'graph_hud', 'graph_debug', 'graph_vfx'}

        perf_strs = [
            make_title('GUI Performance', length=30),
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            f'View size: {list(round(_) for _ in self.enc.size)}',
            f'Map zoom: {self.enc.zoom_str} ({self.enc.upp:.2f} u/p)',
            f'Units: {len(self.api.units)} (drawing: {self.enc.overlays["sprites"].drawn_count})',
            f'vfx count: {len(self.api.get_visual_effects())}',
        ]
        for tname, timer in self.enc.timers.items():
            if isinstance(timer, RateCounter):
                if tname in bold:
                    perf_strs.append(f'[b]{tname}: {timer.mean_elapsed_ms:.3f} ms[/b]')
                else:
                    perf_strs.append(f'{tname}: {timer.mean_elapsed_ms:.3f} ms')
        perf_text = '\n'.join(perf_strs)
        texts = [*self.api.debug_panel_labels()]
        texts[0] = '\n'.join((perf_text, texts[0]))

        for i, text in enumerate(texts):
            panel = self.panels[i]
            panel.text = text
            w = int(self.main_panel.size[0]/len(texts))
            panel.text_size = w, self.main_panel.size[1]
            panel.size_hint = 1, 1
            panel.set_size(x=w)
