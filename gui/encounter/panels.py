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

from data import TITLE, DEV_BUILD
from data.assets import Assets
from data.settings import PROFILE
from gui import cc_int, center_position
from gui.api import MOUSE_EVENTS, ControlEvent, InputEvent
from gui.common import SpriteLabel, CenteredSpriteBox, SpriteTitleLabel, SpriteBox, Stack, Modal
from gui.encounter import EncounterViewComponent

from logic.common import *


Box = namedtuple('Box', ['box', 'sprite', 'label'])


class ControlButton(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='top', **kwargs)
        self.button = self.add(widgets.Image(
            source=Assets.get_sprite('ui.menu'),
            allow_stretch=True))
        self.button.set_size(x=25, y=25)
        self.button.bind(on_touch_down=self.on_touch_down)

    def update(self):
        pass

    def on_touch_down(self, m):
        if not m.button == 'left':
            return False
        if self.button.collide_point(*m.pos):
            self.enc.interface.append(ControlEvent('toggle_menu', 0, ''))
            return True
        return False


class LogicLabel(widgets.AnchorLayout, EncounterViewComponent):
    overlay_height = 50
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='top', **kwargs)
        self.main_frame = main_frame = self.add(widgets.BoxLayout())
        main_frame.make_bg((1,1,1,1), source=Assets.get_sprite('ui.panel-top'))
        main_frame.set_size(y=self.overlay_height)

        self.labels = []
        for i in range(4):
            l = widgets.Label(halign='center', valign='top', outline_width=2)
            main_frame.add(l)
            self.labels.append(l)

        a = main_frame.add(widgets.AnchorLayout(anchor_y='top'))
        self.debug_label = a.add(widgets.Label(halign='center', valign='top', outline_width=2))
        self.debug_label.set_size(x=250 if DEV_BUILD else 160, y=25)
        self.debug_label.make_bg((0,0,0,0), source=Assets.get_sprite('ui.mask-4x1'))

        self.enc.interface.register('set_top_panel_labels', self.set_labels)
        self.enc.interface.register('set_top_panel_color', self.set_color)

    def update(self):
        frame_str = f' ({self.enc.total_timers["frame_total"].mean_elapsed_ms:.2f} ms)' if DEV_BUILD else ''
        self.debug_label.text = f'{TITLE} | {round(self.app.fps.rate)} FPS{frame_str}'
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
        self.frames = {}
        for side in ('left', 'right'):
            anchor = self.add(widgets.AnchorLayout(anchor_x=side, anchor_y='center'))
            frame = anchor.add(widgets.BoxLayout())
            frame.set_size(x=40)
            self.frames[side] = frame
        self.bind(pos=self.reposition, size=self.reposition)
        self.enc.settings_notifier.subscribe('ui.decoration_color', self.setting_decorations)
        self.setting_decorations()

    def setting_decorations(self):
        for side, frame in self.frames.items():
            color = PROFILE.get_setting('ui.decoration_color')
            frame.make_bg(color, source=Assets.get_sprite(f'ui.side-{side}'))

    def reposition(self, *a):
        self.pos = self.enc.pos
        self.size = self.enc.size


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='center', anchor_y='bottom', **kwargs)
        touch_consumer = self.add(widgets.ConsumeTouch(consume_keys=False))

        self.main_frame = self.add(widgets.BoxLayout())

        self.portrait_frame = self.main_frame.add(widgets.BoxLayout(orientation='vertical'))
        self.portrait_frame.make_bg((1,1,1,1), source=Assets.get_sprite('ui.portrait'))
        self.portrait_frame.bind(on_touch_down=self.portrait_click)
        self.name_label = self.portrait_frame.add(widgets.Label(halign='center', valign='middle'))
        self.portrait = self.portrait_frame.add(widgets.Image(allow_stretch=True, keep_ratio=True))
        self.name_label.set_size(y=25)
        self.name_label.text_size = self.name_label.size
        self.center_frame = self.main_frame.add(widgets.BoxLayout(orientation='vertical'))

        self.status_anchor = self.center_frame.add(widgets.AnchorLayout(anchor_x='left', anchor_y='bottom'))
        self.status_stack = self.status_anchor.add(Stack(
            name='HUD Status', wtype=CenteredSpriteBox,
            callback=lambda i, b: self.click('status', i, b),
            consume_box_touch=False,
        ))
        self.status_stack.make_bg((0,0,0,0))

        center_frame_no_status = self.center_frame.add(widgets.BoxLayout(orientation='vertical'))
        touch_consumer.widget = center_frame_no_status
        self.bar_frame = center_frame_no_status.add(widgets.BoxLayout(orientation='vertical'))
        s = Assets.get_sprite('ui.stat-bar')
        self.bars = [self.bar_frame.add(widgets.Progress(source=s)) for _ in range(2)]

        self.main_panel = center_frame_no_status.add(widgets.BoxLayout())

        self.left_panel = self.main_panel.add(widgets.AnchorLayout())
        self.left_panel.make_bg((1,1,1,1), source=Assets.get_sprite('ui.hud-left'))
        self.left_hud = self.left_panel.add(Stack(
            name='HUD left',
            wtype=lambda *a, **k: CenteredSpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui.sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui.sprite-box'),
                **k),
            callback=lambda i, b: self.click('left', i, b),
            drag_drop_callback=lambda *a: self.hud_drag_drop('left', *a),
        ))

        self.middle_panel = self.main_panel.add(widgets.BoxLayout(orientation='vertical'))
        self.middle_panel.make_bg((1,1,1,1), source=Assets.get_sprite('ui.hud-middle'))
        middle_hud_anchor = self.middle_panel.add(widgets.AnchorLayout())
        self.middle_hud = middle_hud_anchor.add(Stack(
            name='HUD middle', wtype=SpriteLabel,
            callback=lambda i, b: self.click('middle', i, b)))
        self.middle_label = self.middle_panel.add(widgets.Label(halign='center', valign='middle'))
        self.middle_label.make_bg((0,0,0,0.3), source=Assets.get_sprite('ui.mask-4x1'))

        self.right_panel = self.main_panel.add(widgets.AnchorLayout())
        self.right_panel.make_bg((1,1,1,1), source=Assets.get_sprite('ui.hud-right'))
        self.right_hud = self.right_panel.add(Stack(
            name='HUD right',
            wtype=lambda *a, **k: CenteredSpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui.sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui.sprite-box'),
                **k),
            callback=lambda i, b: self.click('right', i, b),
            drag_drop_callback=lambda *a: self.hud_drag_drop('right', *a),
        ))

        self.enc.interface.register('set_huds', self.set_huds)
        self.enc.interface.register('set_hud_bars', self.set_hud_bars)
        self.enc.interface.register('set_hud_portrait', self.set_portrait)
        self.enc.interface.register('set_hud_middle_label', self.set_middle_label)

        self.enc.settings_notifier.subscribe('ui.hud_height', self.setting_hud_scale)
        self.enc.settings_notifier.subscribe('ui.hud_width', self.setting_hud_scale)
        self.setting_hud_scale()
        self.enc.settings_notifier.subscribe('ui.detailed_mode', self.set_auto_hover)
        self.enc.settings_notifier.subscribe('ui.auto_tooltip', self.set_auto_hover)
        self.set_auto_hover()

    def update(self):
        pass

    def hud_drag_drop(self, hud, origin, target, button):
        mouse_event = MOUSE_EVENTS[button]
        if mouse_event == 'select':
            self.enc.interface.append(ControlEvent(f'{hud}_hud_drag_drop', (origin, target), 'Index is tuple of (origin_index, target_index)'))

    def portrait_click(self, w, m):
        if not self.portrait_frame.collide_point(*m.pos):
            return
        self.enc.interface.append(ControlEvent(f'hud_portrait_{MOUSE_EVENTS[m.button]}', 0, ''))
        return True

    def click(self, hud, index, button):
        self.enc.interface.append((ControlEvent(f'{hud}_hud_{MOUSE_EVENTS[button]}', index, '')))

    @property
    def hud_visible(self):
        return self.main_frame in self.children

    def set_auto_hover(self):
        set_as = None
        if PROFILE.get_setting('ui.detailed_mode') and PROFILE.get_setting('ui.auto_tooltip'):
            set_as = 'middle'
        self.middle_hud.hover_invokes = set_as
        self.right_hud.hover_invokes = set_as
        self.left_hud.hover_invokes = set_as
        self.status_stack.hover_invokes = set_as

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
        self.status_stack.update(statuses)

    def set_middle_label(self, text):
        self.middle_label.text = text

    def setting_hud_scale(self):
        width_scale = PROFILE.get_setting('ui.hud_width') * 2
        height_scale = PROFILE.get_setting('ui.hud_height') * 2

        status_size = 50 * sum((width_scale, height_scale))/2
        middle_width = 230 * width_scale
        side_width = 300 * width_scale
        side_height = 120 * height_scale
        bar_height = 64 * (height_scale / 2)
        bar_width = side_width * 2 + middle_width
        portrait_size = side_height + bar_height
        total_width = bar_width + portrait_size
        self.overlay_height = total_height = portrait_size + status_size

        self.main_frame.set_size(x=total_width, y=total_height)
        self.center_frame.set_size(x=bar_width, y=total_height)
        self.status_anchor.set_size(y=status_size)
        self.status_stack.set_size(x=bar_width, y=status_size)
        self.status_stack.set_boxsize((status_size, status_size))
        self.portrait_frame.set_size(x=portrait_size, y=portrait_size)
        self.bar_frame.set_size(y=bar_height)
        self.left_panel.set_size(side_width, side_height)
        self.left_hud.set_boxsize((side_width/4, side_height/2))
        self.middle_panel.set_size(middle_width, side_height)
        self.middle_hud.set_boxsize((middle_width/3, side_height/4))
        self.right_panel.set_size(side_width, side_height)
        self.right_hud.set_boxsize((side_width/4, side_height/2))
        self.middle_label.set_size(y=side_height/4)


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
            name='Browse',
            wtype=lambda *a, **k: SpriteBox(*a,
                bg_sprite=Assets.get_sprite('ui.sprite-box-mask'),
                fg_sprite=Assets.get_sprite('ui.sprite-box'),
                valign='bottom', **k),
            x=item_box_size, y=item_box_size,
            callback=self.click))
        self.stack.set_size(stack_size, main_height)
        self.stack.make_bg((0,0,0,0.5))

        self.frame.set_size(x=main_width+stack_size, y=main_height)
        self.set_frame(self.frame)
        self.enc.interface.register('browse_showing', lambda: self.activated)
        self.enc.interface.register('browse_show', self.activate)
        self.enc.interface.register('browse_hide', self.deactivate)
        self.enc.interface.register('browse_toggle', self.toggle)
        self.enc.interface.register('set_browse_main', self.set_browse_main)
        self.enc.interface.register('set_browse_elements', self.set_browse_elements)
        self.enc.settings_notifier.subscribe('ui.detailed_mode', self.set_auto_hover)
        self.enc.settings_notifier.subscribe('ui.auto_tooltip', self.set_auto_hover)
        self.set_auto_hover()

    def click(self, index, button):
        self.enc.interface.append(ControlEvent(f'modal_{MOUSE_EVENTS[button]}', index, ''))

    def activate(self):
        super().activate()
        self.enc.tooltip.deactivate()
        self.set_auto_hover()

    def deactivate(self):
        super().deactivate()
        self.enc.tooltip.deactivate()
        self.set_auto_hover()

    def update(self):
        pass

    def set_browse_main(self, stl):
        self.main.update(stl)

    def set_browse_elements(self, spriteboxes):
        self.stack.update(spriteboxes)

    def click_dismiss(self):
        self.enc.interface.append(ControlEvent('toggle_shop', 0, ''))

    def set_auto_hover(self):
        if not self.activated:
            self.stack.hover_invokes = None
            return
        if PROFILE.get_setting('ui.detailed_mode') and PROFILE.get_setting('ui.auto_tooltip'):
            self.stack.hover_invokes = 'middle'
        else:
            self.stack.hover_invokes = None


class ViewFade(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='top', **kwargs)
        self.enc.interface.register('set_view_fade', self.set_view_fade)

    def update(self):
        pass

    def set_view_fade(self, fade):
        self.make_bg((0, 0, 0, fade))


class Menu(Modal, EncounterViewComponent):
    active_bg = (0,0,0,0.6)
    RESUME_TEXT = 'Resume'
    MINIMIZE_TEXT = 'Settings'
    LEAVE_TEXT = 'Leave'
    LEAVE_CONFIRM_TEXT = 'Leave the encounter?'
    QUIT_TEXT = 'Quit'
    QUIT_CONFIRM_TEXT = 'Quit to desktop?'
    BUTTON_HEIGHT = 35

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_dismiss = False
        self.frame = widgets.BoxLayout(orientation='vertical')
        self.set_frame(self.frame)
        self.consume_touch.widget = self
        self.frame.set_size(x=200, y=250)
        self.frame.make_bg((0, 0, 0, 1), source=Assets.get_sprite('ui.mask-1x2'))

        self.label = self.frame.add(widgets.Label(
            halign='center', valign='middle',
            markup=True, line_height=1.2))

        b = widgets.Button(text=self.RESUME_TEXT, on_release=lambda *a: self.click_resume())
        b.set_size(y=self.BUTTON_HEIGHT)
        self.frame.add(b)
        b = widgets.Button(text=self.MINIMIZE_TEXT, on_release=lambda *a: self.click_home())
        self.frame.add(b)
        b.set_size(y=self.BUTTON_HEIGHT)
        self.leave_text = self.LEAVE_TEXT
        self.leave_confirm_text = self.LEAVE_CONFIRM_TEXT
        self.leave_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_leave()))
        self.leave_btn.set_size(y=self.BUTTON_HEIGHT)
        self.quit_btn = self.frame.add(widgets.Button(on_release=lambda *a: self.click_quit()))
        self.quit_btn.set_size(y=self.BUTTON_HEIGHT)

        self.confirm_leave = False
        self.confirm_quit = False
        self.unconfirm()
        self.enc.interface.register('menu_showing', lambda: self.activated)
        self.enc.interface.register('menu_show', self.activate)
        self.enc.interface.register('menu_hide', self.deactivate)
        self.enc.interface.register('set_menu_text', self.set_text)
        self.enc.interface.register('set_menu_home_text', self.set_home_text)
        self.enc.interface.register('set_menu_leave_text', self.set_leave_text)

    def set_home_text(self, text):
        self.home_btn.text = text

    def set_leave_text(self, text, confirm_text):
        self.leave_text, self.leave_confirm_text = text, confirm_text
        self.leave_btn.text = confirm_text if self.confirm_leave else text

    def click_resume(self):
        self.enc.interface.append(ControlEvent('toggle_menu', 0, self.RESUME_TEXT))
        self.unconfirm()

    def click_home(self):
        self.app.switch_screen('profile')
        self.unconfirm()

    def activate(self):
        self.unconfirm()
        self.make_bg(self.active_bg)
        super().activate()

    def deactivate(self):
        super().deactivate()
        self.make_bg((0,0,0,0))
        self.unconfirm()

    def unconfirm(self):
        self.confirm_leave = False
        self.leave_btn.text = self.leave_text
        self.confirm_quit = False
        self.quit_btn.text = self.QUIT_TEXT

    def click_leave(self):
        if self.confirm_leave:
            self.app.interface.append(ControlEvent('leave_encounter', 0, self.leave_btn.text))
        else:
            self.unconfirm()
            self.confirm_leave = True
            self.leave_btn.text = self.leave_confirm_text

    def click_quit(self):
        if self.confirm_quit:
            self.app.do_quit()
        else:
            self.unconfirm()
            self.confirm_quit = True
            self.quit_btn.text = self.QUIT_CONFIRM_TEXT

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
        def display_timer_collection(collection):
            strs = []
            for tname, timer in collection.items():
                if isinstance(timer, RateCounter):
                    m = timer.mean_elapsed_ms
                    if m > 0.5:
                        strs.append(f'[b]{tname}: {m:.3f} ms[/b]')
                    else:
                        strs.append(f'{tname}: {m:.3f} ms')
            return '\n'.join(strs)

        texts = list(texts)
        perf_strs = [
            make_title('GUI Performance', length=30),
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            f'View size: {list(round(_) for _ in self.enc.size)}',
            f'Mouse position: {tuple(int(_) for _ in self.app.mouse_pos)}',
            f'Mouse real position: {tuple(round(_,2) for _ in self.enc.mouse_real_pos)}',
            f'Map zoom: {self.enc.zoom_str} ({self.enc.upp:.2f} u/p)',
            f'Unit sprites: {len(self.enc.overlays["sprites"].sprites)} (drawing: {self.enc.overlays["sprites"].visible_count})',
            f'VFX count: {self.enc.overlays["vfx"].vfx_count}',
            make_title('Totals', length=30),
            display_timer_collection(self.enc.total_timers),
            make_title('Singles', length=30),
            display_timer_collection(self.enc.single_timers),
        ]

        perf_text = '\n'.join(perf_strs)
        texts[0] = '\n'.join((perf_text, texts[0]))

        w = int(self.main_panel.size[0]/len(texts))
        for i, text in enumerate(texts):
            panel = self.panels[i]
            panel.text = text
            panel.text_size = w, self.main_panel.size[1]
            panel.size_hint = 1, 1
            panel.set_size(x=w)
