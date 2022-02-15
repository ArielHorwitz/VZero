import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import numpy as np
from nutil.vars import modify_color
from nutil.kex import widgets
from data.assets import Assets
from data.settings import Settings


TOOLTIP_SIZE = 400, 600


class CenteredSpriteBox(widgets.AnchorLayout):
    def __init__(self,
            size_hint=(.9, .9),
            bg_sprite=None, fg_sprite=None, valign=None,
            **kwargs):
        super().__init__(**kwargs)
        self.sb = self.add(SpriteBox(bg_sprite=bg_sprite, fg_sprite=fg_sprite, valign=valign))
        self.sb.size_hint = size_hint

    def update(self, *a, **k):
        self.sb.update(*a, **k)


class SpriteBox(widgets.Widget):
    def __init__(self,
            sprite=None, text='',
            bg_sprite=None, fg_sprite=None,
            margin=None, valign=None,
            **kwargs):
        valign = 'center' if valign is None else valign
        super().__init__(**kwargs)
        if sprite is None:
            sprite = str(Assets.FALLBACK_SPRITE)
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
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
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
            margin=None, **kwargs):
        super().__init__(**kwargs)
        self.margin = (0.98, 0.9) if margin is None else margin
        self.main = self.add(widgets.BoxLayout())
        if sprite is None:
            sprite = str(Assets.FALLBACK_SPRITE)
        self.sprite_source = sprite
        self.sprite = self.main.add(widgets.Image(source=sprite, allow_stretch=True))
        self.label = self.main.add(widgets.Label(text=text, halign='center', valign='center'))
        self.main.make_bg((0,0,0,0) if bg_mask_color is None else bg_mask_color)
        self.main._bg.source = Assets.get_sprite('ui', 'mask-4x1') if bg_mask is None else bg_mask
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.sprite.set_size(x=min(self.size[1], self.size[0]/3))
        self.main.set_size(self.size[0]*self.margin[0], self.size[1]*self.margin[1])

    def update(self, sl):
        if sl.sprite != self.sprite_source and sl.sprite is not None:
            self.sprite.source = self.sprite_source = sl.sprite
        self.label.text = sl.text
        self.label.text_size = self.label.size
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
        self._bg.source = Assets.get_sprite('ui', 'mask-1x2')
        if sprite is None:
            sprite = str(Assets.FALLBACK_SPRITE)

        top = self.main_frame.add(widgets.BoxLayout())
        top.set_size(y=50)
        top.make_bg((0,0,0,0.2) if top_bg is None else top_bg)
        top._bg.source = Assets.get_sprite('ui', 'mask-4x1')
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
        self.bind(size=self.reposition, pos=self.reposition)

    def reposition(self, *a):
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
    def __init__(self,
            wtype=None, x=None, y=None,
            callback=None,
            drag_drop_callback=None,
            consider_hover=False,
            **kwargs):
        super().__init__(**kwargs)
        self.__wtype = SpriteLabel if wtype is None else wtype
        self.__x = 250 if x is None else x
        self.__y = 50 if y is None else y
        self.boxes = []
        self.callback = callback
        self.drag_drop_callback = drag_drop_callback
        self.dragging = None
        self.consider_hover = consider_hover
        self.make_bg((0, 0, 0, 1))
        if self.callback or self.drag_drop_callback:
            self.bind(on_touch_down=lambda w, m: self.on_touch_down(m))
        if self.drag_drop_callback:
            self.bind(on_touch_up=lambda w, m: self.on_touch_up(m))
        widgets.kvWindow.bind(mouse_pos=self.check_hover)

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
        if not self.consider_hover:
            return False
        if not self.collide_point(*pos):
            return False
        for i, b in enumerate(self.boxes):
            if b.collide_point(*pos):
                self.callback(i, 'left')
                break
        return False

    def on_touch_down(self, m):
        if not self.collide_point(*m.pos):
            return False
        for i, b in enumerate(self.boxes):
            if b.collide_point(*m.pos):
                self.callback(i, m.button)
                if self.drag_drop_callback:
                    self.dragging = i
                break
        return True

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


class Tooltip(widgets.BoxLayout):
    def __init__(self, bounding_widget=None, **kwargs):
        super().__init__(**kwargs)
        self.bounding_widget = bounding_widget
        self.__frame = widgets.AnchorLayout()
        self.stl = self.__frame.add(SpriteTitleLabel(text_color=(0,0,0,1), top_bg=(0,0,0,0)))
        self.stl.set_size(hx=0.96, hy=0.9)
        self.__frame.set_size(*TOOLTIP_SIZE)
        self.__frame.make_bg(modify_color((1,1,1), v=0.85))
        self.__frame._bg.source = Assets.get_sprite('ui', 'tooltip')
        self.bind(on_touch_down=self._check_click)
        self.__hover_bind = None
        self.__dismiss_origin = np.array([0, 0])
        self.auto_dismiss = Settings.get_setting('auto_dismiss_tooltip', 'UI')

    def activate(self, pos, stl, bounding_widget=None):
        if self.__frame not in self.children:
            self.add(self.__frame)
            pos = np.array(pos) - self.__frame.size
            if bounding_widget is None:
                bounding_widget = self.bounding_widget
            if bounding_widget is not None:
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
        if m.button == 'left' and self.__frame in self.children:
            self.deactivate()
            return True

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
        self.consume_touch.widget = self.__frame

    def activate(self):
        self.consume_touch.enable = True
        if self.__frame not in self.children:
            self.add(self.__frame)

    def deactivate(self):
        self.consume_touch.enable = False
        if self.__frame in self.children:
            self.remove_widget(self.__frame)

    def _check_click(self, w, m):
        if self.auto_dismiss is True and m.button == 'left':
            if not self.__frame.collide_point(*m.pos):
                self.deactivate()
