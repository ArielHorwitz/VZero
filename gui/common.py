import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from data.assets import Assets


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


class STLStack(widgets.GridLayout):
    def __init__(self, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.boxes = []
        self.callback = callback

    def reset_box_count(self, count):
        if count > len(self.boxes):
            self.boxes.extend([self.add(SpriteTitleLabel()) for _ in range(count-len(self.boxes))])
        elif count < len(self.boxes):
            remove_boxes = self.boxes[count:]
            for b in remove_boxes:
                self.remove_widget(b)
                self.boxes.remove(b)
        self.cols = int(len(self.boxes)**.5*1.5)

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

    def update(self, stls):
        if len(stls) != len(self.boxes):
            self.reset_box_count(len(stls))
        for i, stl in enumerate(stls):
            self.boxes[i].update(stl)
