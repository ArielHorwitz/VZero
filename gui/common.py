import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import numpy as np
from nutil.kex import widgets
from data.assets import Assets


class CenteredSpriteBox(widgets.AnchorLayout):
    def __init__(self, size_hint=(.75, .75), **kwargs):
        super().__init__(**kwargs)
        self.sb = self.add(SpriteBox())
        self.sb.size_hint = size_hint

    def update(self, *a, **k):
        self.sb.update(*a, **k)


class SpriteBox(widgets.Widget):
    def __init__(self, sprite=None, text='', **kwargs):
        super().__init__(**kwargs)
        if sprite is None:
            sprite = str(Assets.FALLBACK_SPRITE)
        self.sprite_source = sprite
        self.sprite = self.add(widgets.Image(source=sprite, allow_stretch=True))
        self.make_bg((0,0,0,0))
        with self.canvas:
            self._fg_color = widgets.kvColor(0,0,0,0)
            self._fg = widgets.kvRectangle()
        self.label = self.add(widgets.Label(text=text, halign='center', valign='bottom'))
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.sprite.set_size(*self.size)
        self.label.set_size(*self.size)
        self.label.text_size = self.label.size
        self.sprite.pos = self.pos
        self.label.pos = self.pos
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


class SpriteLabel(widgets.BoxLayout):
    def __init__(self, sprite=None, text='', **kwargs):
        super().__init__(**kwargs)
        if sprite is None:
            sprite = str(Assets.FALLBACK_SPRITE)
        self.sprite_source = sprite
        self.sprite = self.add(widgets.Image(source=sprite, allow_stretch=True))
        self.label = self.add(widgets.Label(text=text, halign='center', valign='center'))
        self.make_bg((0, 0, 0, 0))
        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.sprite.set_size(x=min(self.size[1], self.size[0]/3))

    def update(self, sl):
        if sl.sprite != self.sprite_source and sl.sprite is not None:
            self.sprite.source = self.sprite_source = sl.sprite
        self.label.text = sl.text
        self.label.text_size = self.label.size
        if sl.color is not None:
            self._bg_color.rgba = sl.color


class SpriteTitleLabel(widgets.BoxLayout):
    def __init__(self,
        sprite=None, title='', text='',
        orientation='vertical', **kwargs
    ):
        super().__init__(orientation=orientation, **kwargs)
        self.make_bg((0, 0, 0, 0))
        if sprite is None:
            sprite = str(Assets.FALLBACK_SPRITE)

        top = self.add(widgets.BoxLayout())
        top.set_size(y=50)
        top.make_bg((0, 0, 0, 0.2))
        self.sprite_source = sprite
        self.sprite = top.add(widgets.Image(source=sprite, allow_stretch=True))
        self.sprite.set_size(x=50)
        self.title = top.add(widgets.Label(text=title, halign='center', valign='center'))
        self.label = self.add(widgets.Label(text=text, halign='left', valign='top'))

    def update(self, stl):
        if stl.sprite != self.sprite_source and stl.sprite is not None:
            self.sprite.source = self.sprite_source = stl.sprite
        self.title.text = stl.title
        self.title.text_size = self.title.size
        self.label.text = stl.label
        self.label.text_size = self.label.size
        if stl.color is not None:
            self._bg_color.rgba = stl.color


class Stack(widgets.StackLayout):
    def __init__(self,
        wtype=None,
        callback=None, on_hover=None,
        x=None, y=None,
        **kwargs):
        super().__init__(**kwargs)
        self.__wtype = SpriteLabel if wtype is None else wtype
        self.__x = 250 if x is None else x
        self.__y = 50 if y is None else y
        self.boxes = []
        self.callback = callback
        self.__on_hover = on_hover
        self.make_bg((0, 0, 0, 1))
        if self.callback is not None:
            self.bind(on_touch_down=lambda w, m: self.on_touch_down(m))

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

    def on_touch_down(self, m):
        if self.callback is None:
            return False
        if not self.collide_point(*m.pos):
            return False
        for i, b in enumerate(self.boxes):
            if b.collide_point(*m.pos):
                self.callback(i, m.button)
                break
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
        self.__frame = SpriteTitleLabel()
        self.__frame.set_size(300, 250)
        self.set_size(300, 250)
        self.bind(on_touch_down=self._check_click)

    def activate(self, pos, stl, bounding_widget=None):
        if self.__frame not in self.children:
            self.add(self.__frame)
            if bounding_widget is None:
                bounding_widget = self.bounding_widget
            if bounding_widget is not None:
                fix = np.zeros(2) - 5
                if not bounding_widget.collide_point(*pos):
                    blfix = np.array(bounding_widget.pos) - pos
                    blfix[blfix<0] = 0
                    fix += blfix
                if not bounding_widget.collide_point(*(np.array(pos)+self.size)):
                    trfix = (np.array(bounding_widget.pos) + bounding_widget.size) - (np.array(pos) + self.size)
                    trfix[trfix>0] = 0
                    fix += trfix
                pos = tuple(float(_) for _ in (fix + pos))
            self.pos = pos
        self.__frame.update(stl)

    def deactivate(self):
        if self.__frame in self.children:
            self.remove_widget(self.__frame)
            self.pos = -1_000_000, -1_000_000

    def _check_click(self, w, m):
        if m.button == 'left':
            consume = self.__frame in self.children
            self.deactivate()
            return consume


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
