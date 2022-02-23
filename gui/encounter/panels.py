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

from data import TITLE
from data.assets import Assets
from data.settings import Settings
from gui import cc_int, center_position
from gui.api import MOUSE_EVENTS, ControlEvent, InputEvent
from gui.common import SpriteLabel, CenteredSpriteBox, SpriteTitleLabel, SpriteBox, Stack, Modal
from gui.encounter import EncounterViewComponent

from logic.common import *


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
        main_frame.make_bg((1,1,1,1), source=Assets.get_sprite('ui', 'panel-top'))
        main_frame.set_size(y=self.overlay_height)

        self.labels = [main_frame.add(widgets.Label(halign='center', valign='top', outline_width=2)) for i in range(4)]

        a = main_frame.add(widgets.AnchorLayout(anchor_y='top'))
        self.debug_label = a.add(widgets.Label(halign='center', valign='top', outline_width=2))
        self.debug_label.set_size(x=160, y=25)
        self.debug_label.make_bg((0,0,0,0), source=Assets.get_sprite('ui', 'mask-4x1'))

        self.enc.interface.register('set_top_panel_labels', self.set_labels)
        self.enc.interface.register('set_top_panel_color', self.set_color)

    def update(self):
        self.debug_label.text = f'{TITLE} | {round(self.app.fps.rate)} FPS'
        self.debug_label.make_bg(self.app.fps_color)

    def set_color(self, color):
        self.main_frame._bg_color.rgba = color

    def set_labels(self, *texts):
        for i, t in enumerate(texts):
            self.labels[i].text = str(t)

    def set_label(self, index, text):
        self.labels[index].text = str(text)


class Decoration(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for side in ('left', 'right'):
            anchor = self.add(widgets.AnchorLayout(anchor_x=side, anchor_y='center'))
            frame = anchor.add(widgets.BoxLayout())
            frame.make_bg((1,1,1,Settings.get_setting('decorations', 'UI')), source=Assets.get_sprite('ui', f'side-{side}'))
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
        portrait_frame.make_bg((1,1,1,1), source=Assets.get_sprite('ui', 'portrait'))
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
        self.bars = [bars.add(widgets.Progress(source=s)) for _ in range(2)]

        main_panel = center_frame.add(widgets.BoxLayout())
        main_panel.set_size(y=HUD_HEIGHT)

        padding = 0.95, 0.95
        left_panel = main_panel.add(widgets.AnchorLayout())
        left_panel.set_size(HUD_WIDTH, HUD_HEIGHT).make_bg((1,1,1,1), source=Assets.get_sprite('ui', 'hud-left'))
        self.left_hud = left_panel.add(Stack(
            wtype=lambda *a, **k: CenteredSpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui', 'sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui', 'sprite-box'),
                **k),
            callback=lambda i, b: self.click('left', i, b),
            drag_drop_callback=lambda *a: self.hud_drag_drop('left', *a),
            x=HUD_WIDTH*padding[0]/4, y=HUD_HEIGHT*padding[1]/2))
        self.left_hud.set_size(hx=padding[0], hy=padding[1])

        middle_panel = main_panel.add(widgets.BoxLayout(orientation='vertical'))
        middle_panel.set_size(x=MIDDLE_HUD).make_bg((1,1,1,1), source=Assets.get_sprite('ui', 'hud-middle'))
        middle_hud_anchor = middle_panel.add(widgets.AnchorLayout())
        middle_hud_size = MIDDLE_HUD*padding[0], HUD_HEIGHT*padding[1]*0.75
        self.middle_hud = middle_hud_anchor.add(Stack(
            wtype=SpriteLabel, callback=lambda i, b: self.click('middle', i, b),
            x=middle_hud_size[0]/3, y=middle_hud_size[1]/3))
        self.middle_hud.set_size(x=middle_hud_size[0], y=middle_hud_size[1])
        self.middle_label = middle_panel.add(widgets.Label(halign='center', valign='middle'))
        self.middle_label.make_bg((0,0,0,0.3), source=Assets.get_sprite('ui', 'mask-4x1'))
        self.middle_label.set_size(y=HUD_HEIGHT-middle_hud_size[1])

        right_panel = main_panel.add(widgets.AnchorLayout())
        right_panel.set_size(HUD_WIDTH, HUD_HEIGHT).make_bg((1,1,1,1), source=Assets.get_sprite('ui', 'hud-right'))
        self.right_hud = right_panel.add(Stack(
            wtype=lambda *a, **k: CenteredSpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui', 'sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui', 'sprite-box'),
                **k),
            callback=lambda i, b: self.click('right', i, b),
            drag_drop_callback=lambda *a: self.hud_drag_drop('right', *a),
            x=HUD_WIDTH*padding[0]/4, y=HUD_HEIGHT*padding[1]/2))
        self.right_hud.set_size(hx=padding[0], hy=padding[1])

        self.enc.interface.register('set_huds', self.set_huds)
        self.enc.interface.register('set_hud_bars', self.set_hud_bars)
        self.enc.interface.register('set_hud_portrait', self.set_portrait)
        self.enc.interface.register('set_hud_middle_label', self.set_middle_label)
        self.bind(pos=self.reposition, size=self.reposition)

    def update(self):
        self.set_auto_hover(self.enc.detailed_info_mode if self.hud_visible else False)

    def hud_drag_drop(self, hud, origin, target, button):
        if button == 'middle':
            self.enc.interface.append(ControlEvent(f'{hud}_hud_drag_drop', (origin, target), 'Index is tuple of (origin_index, target_index)'))

    def portrait_click(self, w, m):
        if not self.portrait_frame.collide_point(*m.pos):
            return
        self.enc.interface.append(ControlEvent(f'hud_portrait_{MOUSE_EVENTS[m.button]}', 0, ''))

    def click(self, hud, index, button):
        self.enc.interface.append((ControlEvent(f'{hud}_hud_{MOUSE_EVENTS[button]}', index, '')))

    def reposition(self, *a):
        self.anchor_x = 'left' if self.enc.size[0] < TOTAL_HUD_WIDTH else 'center'
        self.name_label.text_size = self.name_label.size

    def show_hud(self):
        if not self.hud_visible:
            self.add(self.main_frame)

    def hide_hud(self):
        self.set_auto_hover(False)
        if self.hud_visible:
            self.remove_widget(self.main_frame)

    @property
    def hud_visible(self):
        return self.main_frame in self.children

    def set_auto_hover(self, set_as=None):
        if not AUTO_TOOLTIP:
            return
        set_as = self.enc.detailed_info_mode if set_as is None else set_as
        self.middle_hud.consider_hover = set_as
        self.right_hud.consider_hover = set_as
        self.left_hud.consider_hover = set_as
        self.status_panel.consider_hover = set_as

    def set_hud_bars(self, top, bottom):
        for i, pb in enumerate((top, bottom)):
            self.bars[i].progress = pb.value
            self.bars[i].text = pb.text
            self.bars[i].fg_color = pb.color

    def set_portrait(self, source, label):
        self.portrait.source = source
        self.name_label.text = label

    def set_huds(self, left, middle, right, statuses):
        self.left_hud.update(left)
        self.middle_hud.update(middle)
        self.right_hud.update(right)
        self.status_panel.update(statuses)
        self.status_panel.set_size(x=len(self.status_panel.boxes)*50)

    def set_middle_label(self, text):
        self.middle_label.text = text


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
        self.enc.interface.register('browse_showing', lambda: self.activated)
        self.enc.interface.register('browse_show', self.show)
        self.enc.interface.register('browse_hide', self.hide)
        self.enc.interface.register('set_browse_main', self.set_browse_main)
        self.enc.interface.register('set_browse_elements', self.set_browse_elements)

    def click(self, index, button):
        self.enc.interface.append(ControlEvent(f'modal_{MOUSE_EVENTS[button]}', index, ''))

    def show(self):
        self.activate()
        self.enc.tooltip.deactivate()

    def hide(self):
        self.deactivate()
        self.enc.tooltip.deactivate()

    def update(self):
        if not self.activated:
            self.stack.consider_hover = False
            return
        self.stack.consider_hover = self.enc.detailed_info_mode if AUTO_TOOLTIP else False

    def set_browse_main(self, stl):
        self.main.update(stl)

    def set_browse_elements(self, spriteboxes):
        self.stack.update(spriteboxes)


class ViewFade(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.enc.interface.register('set_view_fade', self.set_view_fade)

    def update(self):
        pass

    def set_view_fade(self, fade):
        self.make_bg((0, 0, 0, fade))


class Menu(Modal, EncounterViewComponent):
    active_bg = (0,0,0,0.6)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_dismiss = False
        self.frame = widgets.BoxLayout(orientation='vertical')
        self.set_frame(self.frame)
        self.consume_touch.widget = self
        self.frame.set_size(x=200, y=250)
        self.frame.make_bg((0, 0, 0, 1), source=Assets.get_sprite('ui', 'mask-1x2'))

        self.label = self.frame.add(widgets.Label(text='', halign='center', valign='middle', markup=True, line_height=1.2))
        self.label.set_size(y=100)

        self.frame.add(widgets.Button(text=RESUME_TEXT, on_release=lambda *a: self.click_resume()))
        self.restart_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_restart()))
        self.leave_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_leave()))
        self.quit_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_quit()))

        self.confirm_restart = False
        self.confirm_leave = False
        self.confirm_quit = False
        self.unconfirm()
        self.enc.interface.register('menu_showing', lambda: self.activated)
        self.enc.interface.register('menu_show', self.activate)
        self.enc.interface.register('menu_hide', self.deactivate)
        self.enc.interface.register('set_menu_text', self.set_text)

    def click_resume(self):
        self.enc.interface.append(ControlEvent('toggle_menu', 0, f'Menu "{RESUME_TEXT}" pressed'))

    def activate(self):
        self.unconfirm()
        self.make_bg(self.active_bg)
        super().activate()

    def deactivate(self):
        super().deactivate()
        self.make_bg((0,0,0,0))
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
            self.app.interface.append(ControlEvent('restart_encounter', 0, self.restart_btn.text))
        else:
            self.unconfirm()
            self.confirm_restart = True
            self.restart_btn.text = RESTART_CONFIRM_TEXT

    def click_leave(self):
        if self.confirm_leave:
            self.app.interface.append(ControlEvent('leave_encounter', 0, self.leave_btn.text))
        else:
            self.unconfirm()
            self.confirm_leave = True
            self.leave_btn.text = LEAVE_CONFIRM_TEXT

    def click_quit(self):
        if self.confirm_quit:
            self.app.do_quit()
        else:
            self.unconfirm()
            self.confirm_quit = True
            self.quit_btn.text = QUIT_CONFIRM_TEXT

    def update(self):
        pass

    def set_text(self, text):
        self.label.text = text


class DebugPanel(Modal, EncounterViewComponent):
    bold = {'draw/idle', 'frame_total', 'graphics_total', 'graph_hud', 'graph_debug', 'graph_vfx'}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_panel = widgets.BoxLayout()
        self.set_frame(self.main_panel)
        self.consume_touch.widget = None
        self.main_panel.make_bg(v=0, a=0.5)

        self.panels = []
        for _ in range(10):
            panel = self.main_panel.add(widgets.Label(valign='top', halign='left', markup=True))
            self.panels.append(panel)
            panel.set_size(x=0)

        self.enc.interface.register('debug_showing', self.activated)
        self.enc.interface.register('debug_show', self.activate)
        self.enc.interface.register('debug_hide', self.deactivate)
        self.enc.interface.register('set_debug_panels', self.set_debug_panels)

    def update(self):
        pass

    def set_debug_panels(self, texts):
        texts = list(texts)
        perf_strs = [
            make_title('GUI Performance', length=30),
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            f'View size: {list(round(_) for _ in self.enc.size)}',
            f'Map zoom: {self.enc.zoom_str} ({self.enc.upp:.2f} u/p)',
            f'Unit sprites: {len(self.enc.overlays["sprites"].sprites)} (drawing: {self.enc.overlays["sprites"].visible_count})',
            f'VFX count: {self.enc.overlays["vfx"].vfx_count}',
        ]
        for tname, timer in self.enc.timers.items():
            if isinstance(timer, RateCounter):
                if tname in self.bold:
                    perf_strs.append(f'[b]{tname}: {timer.mean_elapsed_ms:.3f} ms[/b]')
                else:
                    perf_strs.append(f'{tname}: {timer.mean_elapsed_ms:.3f} ms')
        perf_text = '\n'.join(perf_strs)
        texts[0] = '\n'.join((perf_text, texts[0]))

        for i, text in enumerate(texts):
            panel = self.panels[i]
            panel.text = text
            w = int(self.main_panel.size[0]/len(texts))
            panel.text_size = w, self.main_panel.size[1]
            panel.size_hint = 1, 1
            panel.set_size(x=w)
