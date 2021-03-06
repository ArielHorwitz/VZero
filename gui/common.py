import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np
from nutil.vars import modify_color, PublishSubscribe, minmax
from nutil.kex import widgets

from data import APP_NAME
from data.assets import Assets
from data.settings import PROFILE


TOOLTIP_SIZE = 400, 600
SETTINGS_NOTIFIER = PublishSubscribe('GUI common')
PROFILE.register_notifications(SETTINGS_NOTIFIER.push)


class CenteredSpriteBox(widgets.AnchorLayout):
    def __init__(self,
            size_hint=(.9, .9),
            **kwargs):
        super().__init__()
        self.sb = self.add(SpriteBox(**kwargs))
        self.sb.size_hint = size_hint
        self.bind(pos=self.sb.resize, size=self.sb.resize)

    def update(self, *a, **k):
        self.sb.update(*a, **k)


class SpriteBox(widgets.Widget):
    def __init__(self,
            sprite=None, text='',
            bg_sprite=None, fg_sprite=None,
            margin=None, valign=None,
            **kwargs):
        valign = 'bottom' if valign is None else valign
        super().__init__(**kwargs)
        if sprite is None:
            sprite = Assets.FALLBACK_SPRITE
        self.sprite_source = sprite
        self.sprite_frame = self.add(widgets.AnchorLayout())
        self.sprite = self.sprite_frame.add(widgets.Image(source=sprite, allow_stretch=True))
        self.make_bg((1,1,1,1))
        self._bg.source = bg_sprite
        with self.canvas:
            self._fg_color = widgets.kvColor((1,1,1,1))
            self._fg = widgets.kvRectangle(source=fg_sprite)
        self.margin = (0.85, 0.85) if margin is None else margin
        self.label = self.add(widgets.Label(
            text=text, outline_color=(0,0,0,1), outline_width=2,
            halign='center', valign=valign))
        self.bind(pos=self.resize, size=self.resize)

    def resize(self, *a):
        self.sprite_frame.size = self.size
        self.sprite_frame.pos = self.pos
        self.sprite.set_size(x=self.size[0]*self.margin[0], y=self.size[1]*self.margin[1])
        self.sprite.pos = tuple(self.pos[_]+self.size[_]*(1-self.margin[_])/2 for _ in range(2))
        self.label.set_size(*self.size)
        self.label.text_size = self.label.size
        self.label.pos = self.pos[0], self.pos[1]+2
        self._fg.pos = self.pos
        self._fg.size = self.size

    def update(self, sl):
        if sl.sprite != self.sprite_source and sl.sprite is not None:
            self.sprite.source = self.sprite_source = sl.sprite
        self.label.text = sl.label
        if sl.bg_color is not None:
            self._bg_color.rgba = sl.bg_color
        if sl.fg_color is not None:
            self._fg_color.rgba = sl.fg_color


class SpriteLabel(widgets.AnchorLayout):
    def __init__(self, sprite=None, text='',
            bg_mask_color=None, bg_mask=None,
            halign='center', valign='center',
            padding=(2, 2), margin=None,
            **kwargs):
        super().__init__(padding=padding, **kwargs)
        if margin is not None:
            logger.warning(f'SpriteLabel margin will be deprecated. Please use padding instead')
        self.main = self.add(widgets.BoxLayout())
        if sprite is None:
            sprite = Assets.FALLBACK_SPRITE
        self.sprite_source = sprite
        self.sprite = self.main.add(widgets.Image(source=sprite, allow_stretch=True))
        self.label = self.main.add(widgets.Label(text=text, halign=halign, valign=valign, markup=True))
        self.main.make_bg((0,0,0,0) if bg_mask_color is None else bg_mask_color)
        self.main._bg.source = Assets.get_sprite('ui.mask-4x1') if bg_mask is None else bg_mask
        self.label.bind(pos=self.resize, size=self.resize)

    def resize(self, *a):
        sprite_size = min(self.main.size[1], self.main.size[0]/3)
        self.sprite.set_size(x=sprite_size, y=sprite_size)

    def update(self, sl):
        if sl.sprite != self.sprite_source and sl.sprite is not None:
            self.sprite.source = self.sprite_source = sl.sprite
        if sl.text is not None:
            self.label.text = sl.text
        if sl.color is not None:
            self.main._bg_color.rgba = sl.color


class SpriteTitleLabel(widgets.AnchorLayout):
    def __init__(self,
        sprite=None, title='', text='',
        top_bg=None, outline_width=None, text_color=(1,1,1,1),
        **kwargs
    ):
        super().__init__(**kwargs)
        self.make_bg((0,0,0,0))
        self.padding = 0.9, 0.9
        self.main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        self._bg.source = Assets.get_sprite('ui.mask-1x2')
        if sprite is None:
            sprite = Assets.FALLBACK_SPRITE

        top = self.main_frame.add(widgets.BoxLayout())
        top.set_size(y=50)
        top.make_bg((0,0,0,0.2) if top_bg is None else top_bg)
        top._bg.source = Assets.get_sprite('ui.mask-4x1')
        self.sprite_source = sprite
        self.sprite = top.add(widgets.Image(source=sprite, allow_stretch=True))
        self.sprite.set_size(x=50)
        self.title = top.add(widgets.Label(
            text=title, halign='center', valign='center', color=text_color,
            outline_color=(0,0,0,1), outline_width=outline_width, markup=True,
        ))
        self.label = self.main_frame.add(widgets.Label(
            text=text, halign='left', valign='top', color=text_color,
            outline_color=(0,0,0,1), outline_width=outline_width, markup=True,
        ))
        self.bind(size=self.resize, pos=self.resize)

    def resize(self, *a):
        self.main_frame.set_size(
            x=self.size[0]*self.padding[0],
            y=self.size[1]*self.padding[1])

    def update(self, stl):
        if stl.sprite != self.sprite_source and stl.sprite is not None:
            self.sprite.source = self.sprite_source = stl.sprite
        self.title.text = f'[b]{stl.title}[/b]'
        self.title.text_size = self.title.size
        self.label.text = stl.label
        self.label.text_size = self.label.size
        if stl.color is not None:
            self._bg_color.rgba = stl.color


class Stack(widgets.StackLayout):
    def __init__(self, name=None,
            wtype=None, x=None, y=None,
            callback=None,
            consume_box_touch=True,
            consume_stack_touch=False,
            drag_drop_callback=None,
            hover_invokes=None,
            **kwargs):
        self.name = 'Unnamed' if name is None else name
        self.boxes = []
        super().__init__(**kwargs)
        self.__wtype = SpriteLabel if wtype is None else wtype
        self.__x = 250 if x is None else x
        self.__y = 50 if y is None else y
        self.callback = callback
        self.consume_box_touch = consume_box_touch
        self.consume_stack_touch = consume_stack_touch
        self.drag_drop_callback = drag_drop_callback
        self.dragging = None
        self.__hover_invokes = None
        self.__hover_bind = None
        self.__last_hover = None
        self.hover_invokes = hover_invokes
        if self.callback or self.drag_drop_callback:
            self.bind(on_touch_down=lambda w, m: self.on_touch_down(m))
        if self.drag_drop_callback:
            self.bind(on_touch_up=lambda w, m: self.on_touch_up(m))

    def fix_height(self, minimum=0, maximum=float('inf')):
        widget_width = max(1, self.__x)
        max_widgets_row = max(1, int(self.size[0] / widget_width))
        min_rows = math.ceil(len(self.boxes) / max_widgets_row)
        self.height = minmax(minimum, maximum, min_rows * self.__y)

    @property
    def hover_invokes(self):
        return self.__hover_invokes

    @hover_invokes.setter
    def hover_invokes(self, x):
        logger.debug(f'{self} setting hover_invokes: {x}')
        self.__hover_invokes = x
        self.__last_hover = None
        if x is None:
            self._unbind()
        else:
            self._bind()
            self.check_hover(None, widgets.kvWindow.mouse_pos)

    def _bind(self):
        if self.__hover_bind is not None:
            return
        self.__hover_bind = widgets.kvWindow.fbind('mouse_pos', self.check_hover)
        logger.debug(f'{self} binding mouse_pos {self.__hover_bind}')

    def _unbind(self):
        if self.__hover_bind is None:
            return
        logger.debug(f'{self} unbinding mouse_pos {self.__hover_bind}')
        widgets.kvWindow.unbind_uid('mouse_pos', self.__hover_bind)
        self.__hover_bind = None

    def set_boxsize(self, size=None):
        if size is not None:
            self.__x, self.__y = size
        for box in self.boxes:
            box.set_size(self.__x, self.__y)

    def reset_box_count(self, count):
        if count > len(self.boxes):
            self.boxes.extend([self.add(self.__wtype()) for _ in range(count-len(self.boxes))])
        elif count < len(self.boxes):
            remove_boxes = self.boxes[count:]
            for b in remove_boxes:
                self.remove_widget(b)
                self.boxes.remove(b)
        self.set_boxsize()

    def check_hover(self, w, pos):
        if self.hover_invokes is None:
            # Cannot reproduce this issue, so we're trying every contingency and logging
            logger.warning(f'check_hover should only be called if hover_invokes, try unbinding... {w} {self.__hover_bind}')
            if self.__hover_bind is None:
                m = f'check_hover is being called but no fbind_uid found...'
                logger.critical(m)
                raise RuntimeError(m)
            self._unbind()
            return
        pos = self.to_widget(*pos)
        if not self.collide_point(*pos):
            self.__last_hover = None
            return False
        for i, b in enumerate(self.boxes):
            if b.collide_point(*pos):
                if i == self.__last_hover:
                    break
                self.__last_hover = i
                self.callback(i, self.hover_invokes)
                break
        else:
            self.__last_hover = None
        return False

    def on_touch_down(self, m):
        if not self.collide_point(*m.pos):
            return False
        for i, b in enumerate(self.boxes):
            if b.collide_point(*m.pos):
                self.callback(i, m.button)
                if self.drag_drop_callback:
                    self.dragging = i
                return self.consume_box_touch
        return self.consume_stack_touch

    def on_touch_up(self, m):
        if self.dragging is None:
            return False
        for i, b in enumerate(self.boxes):
            if b.collide_point(*m.pos):
                self.drag_drop_callback(self.dragging, i, m.button)
                break
        self.dragging = None
        return True

    def update(self, boxes):
        if len(boxes) != len(self.boxes):
            self.reset_box_count(len(boxes))
        for i, box in enumerate(boxes):
            self.boxes[i].update(box)

    def __repr__(self):
        return f'<Stack {self.name} with {len(self.boxes)} boxes>'


class Tooltip(widgets.BoxLayout):
    def __init__(self,
        bounding_widget=None,
        consume_colliding_touch=False,
        consume_any_touch=False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.bounding_widget = bounding_widget
        self.__frame = widgets.AnchorLayout()
        self.stl = self.__frame.add(SpriteTitleLabel(text_color=(0,0,0,1), top_bg=(0,0,0,0)))
        self.stl.set_size(hx=0.96, hy=0.9)
        self.__frame.set_size(*TOOLTIP_SIZE)
        self.__frame.make_bg(modify_color((1,1,1), v=0.85))
        self.__frame._bg.source = Assets.get_sprite('ui.tooltip')
        self.bind(on_touch_down=self._check_click)
        self.__hover_bind = None
        self.__dismiss_origin = np.array([0, 0])
        self.consume_colliding_touch = consume_colliding_touch
        self.consume_any_touch = consume_any_touch
        SETTINGS_NOTIFIER.subscribe('ui.auto_dismiss_tooltip', self.setting_auto_dismiss)
        self.setting_auto_dismiss()

    def setting_auto_dismiss(self):
        self.auto_dismiss = PROFILE.get_setting('ui.auto_dismiss_tooltip')

    def activate(self, pos, stl, bounding_widget=None):
        if self.__frame not in self.children:
            self.add(self.__frame)
        if bounding_widget is None:
            bounding_widget = self.bounding_widget
        if pos != self.pos:
            pos = np.array(pos) - self.__frame.size
            fix = np.zeros(2)
            if not bounding_widget.collide_point(*pos):
                blfix = np.array(bounding_widget.pos) - pos
                blfix[blfix<0] = 0
                fix += blfix
            if not bounding_widget.collide_point(*(np.array(pos)+self.__frame.size)):
                trfix = (np.array(bounding_widget.pos) + bounding_widget.size) - (np.array(pos) + self.__frame.size)
                trfix[trfix>0] = 0
                fix += trfix
            pos = tuple(float(_) for _ in (fix + pos))
            self.pos = pos
        self.stl.update(stl)
        if self.__hover_bind is not None:
            widgets.kvWindow.unbind_uid('mouse_pos', self.__hover_bind)
        if self.auto_dismiss:
            self.__dismiss_origin = np.array(self.app.mouse_pos)
            self.__hover_bind = widgets.kvWindow.fbind('mouse_pos', self._check_hover)

    def deactivate(self):
        if self.__frame in self.children:
            self.remove_widget(self.__frame)
            self.pos = -1_000_000, -1_000_000
        if self.__hover_bind is not None:
            widgets.kvWindow.unbind_uid('mouse_pos', self.__hover_bind)
            self.__hover_bind = None

    def _check_click(self, w, m):
        if self.__frame in self.children:
            self.deactivate()
            if self.consume_colliding_touch:
                return self.__frame.collide_point(*m.pos)
        return self.consume_any_touch

    def _check_hover(self, w, pos):
        if self.__frame not in self.children:
            return False
        if np.linalg.norm(self.__dismiss_origin - pos) > self.auto_dismiss:
            self.deactivate()


class Modal(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.consume_touch = self.add(widgets.ConsumeTouch(enable=False))
        self.__frame = widgets.Label(text='Popup missing content').set_size(200, 50)
        self.auto_dismiss = True
        self.bind(on_touch_down=self._check_click)

    @property
    def activated(self):
        return self.__frame in self.children

    def set_frame(self, widget):
        if self.__frame in self.children:
            self.remove_widget(self.__frame)
            self.add(widget)
        self.__frame = widget
        self.consume_touch.widget = widget

    def activate(self):
        self.consume_touch.enable = True
        if self.__frame not in self.children:
            self.add(self.__frame)

    def deactivate(self):
        self.consume_touch.enable = False
        if self.__frame in self.children:
            self.remove_widget(self.__frame)

    def toggle(self):
        if self.activated:
            self.deactivate()
        else:
            self.activate()

    def _check_click(self, w, m):
        if self.activated and self.auto_dismiss:
            if not self.__frame.collide_point(*m.pos):
                self.click_dismiss()

    def click_dismiss(self):
        self.deactivate()
