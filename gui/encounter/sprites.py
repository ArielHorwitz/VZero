import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math, copy
import numpy as np
from nutil.time import ratecounter
from nutil.kex import widgets
from gui import cc_int, center_position
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from engine.common import *


MIN_HITBOX_SCALE = 0.25


class Sprites(widgets.RelativeLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.drawn_count = 0
        self.redraw()

    def redraw(self):
        self.sprites = []
        self.last_visible = np.zeros(len(self.api.units), dtype=np.int)
        self.clear_widgets()
        self.canvas.clear()
        for unit in self.api.units:
            s = Sprite(source=unit.sprite)
            s.bar1.fg, s.bar2.fg = self.api.sprite_bar_color(unit.uid)
            s.bar2.bg = (0, 0, 0, 0)
            self.sprites.append(s)

    def update(self):
        visibles = self.api.sprite_visible_mask()
        newly_visible = np.logical_and(visibles == True, np.invert(self.last_visible))
        newly_invisible = np.logical_and(visibles == False, self.last_visible)
        self.last_visible = visibles
        self.drawn_count = visibles.sum()

        all_pos = self.enc.real2pix(self.api.sprite_positions())
        bars1, bars2 = self.api.sprite_bars()
        hp_height = max(5, 10 / self.enc.upp)
        hitboxes = np.array(self.api.sprite_sizes()) * 2 / min(self.enc.upp, (1/MIN_HITBOX_SCALE))

        for uid in np.argwhere(newly_visible):
            uid = uid[0] # np.argwhere returns some nd-shape
            self.canvas.add(self.sprites[uid])

        for uid in np.argwhere(newly_invisible):
            uid = uid[0] # np.argwhere returns some nd-shape
            self.canvas.remove(self.sprites[uid])

        for uid in np.argwhere(visibles):
            with ratecounter(self.enc.timers['sprite_single']):
                uid = uid[0] # np.argwhere returns some nd-shape
                s = self.sprites[uid]
                # Sprite
                size = hitboxes[uid], hitboxes[uid]
                pos = all_pos[uid]
                s.size = size
                s.bar1.progress = bars1[uid]
                s.bar2.progress = bars2[uid]
                s.pos = pos
                s.set_icons(self.api.sprite_statuses(uid))


class Sprite(widgets.kvInstructionGroup):
    def __init__(self, source='', size=(100, 100), **kwargs):
        super().__init__(**kwargs)
        self.sprite = widgets.kvRectangle(source=source, size=size)
        self.bar1 = Bar()
        self.bar2 = Bar()
        self.icons = Icons()
        self.add(self.sprite)
        self.add(self.bar1)
        self.add(self.bar2)
        self.add(self.icons)

    @property
    def set_icons(self):
        return self.icons.set_icons

    @property
    def pos(self):
        return self.sprite.pos

    @pos.setter
    def pos(self, x):
        self.sprite.pos = nx = center_position(x, self.size)
        centered_x = nx[0]+self.size[0]/2
        self.icons.pos = centered_x, nx[1]+self.size[1] + 15
        self.bar1.pos = centered_x, nx[1]+self.size[1] + 7
        self.bar2.pos = centered_x, nx[1]+self.size[1]

    @property
    def size(self):
        return self.sprite.size

    @size.setter
    def size(self, x):
        self.sprite.size = x
        self.bar1.size = self.bar2.size = x[0]*1.5, 5

    @property
    def source(self):
        return self.sprite.source

    @source.setter
    def source(self, x):
        self.sprite.source = x


class Bar(widgets.kvInstructionGroup):
    def __init__(self, size=(50, 5), **kwargs):
        super().__init__(**kwargs)
        self._pos = 0, 0
        self.padding = 3
        self._size = size
        self._progress = 0
        self._bg_color = widgets.kvColor(0,0,0,1)
        self._bg_rect = widgets.kvRectangle(size=size)
        self._fg_color = widgets.kvColor()
        self._fg_rect = widgets.kvRectangle(size=size)
        self.add(self._bg_color)
        self.add(self._bg_rect)
        self.add(self._fg_color)
        self.add(self._fg_rect)

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, x):
        self._pos = x
        adjusted_x = x[0] - self._size[0]/2
        self._bg_rect.pos = adjusted_x-self.padding, self._pos[1]-self.padding
        self._fg_rect.pos = adjusted_x, self._pos[1]

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, size):
        self._size = size[0], size[1]
        self._bg_rect.size = self._size[0]+(self.padding*2), self._size[1]+(self.padding*2)
        self._fg_rect.size = self._size[0]*self._progress, self._size[1]

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, x):
        self._progress = x
        self._fg_rect.size = self._size[0]*self._progress, self._size[1]

    @property
    def fg(self):
        return self._fg_color.rgba

    @fg.setter
    def fg(self, x):
        self._fg_color.rgba = x

    @property
    def bg(self):
        return self._bg_color.rgba

    @bg.setter
    def bg(self, x):
        self._bg_color.rgba = x


class Icons(widgets.kvInstructionGroup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pos = 0, 0
        self._size = 25, 25
        self.add(widgets.kvColor(1,1,1,1))
        self.sprites = []
        self.sources = []

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, x):
        self._pos = x
        if len(self.sprites) == 0:
            return
        centered_x = self._pos[0] - (self._size[0] * len(self.sprites) / 2)
        for i, s in enumerate(self.sprites):
            s.pos = centered_x + i*(self._size[0]+2), self._pos[1]

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, x):
        self._size = x
        for s in self.sprites:
            s.size = x

    def reset_icon_count(self, count):
        if count > len(self.sprites):
            for _ in range(count-len(self.sprites)):
                s = widgets.kvRectangle(size=self.size)
                self.sprites.append(s)
                self.add(s)
        elif count < len(self.sprites):
            remove_sprites = self.sprites[count:]
            for s in remove_sprites:
                self.remove(s)
                self.sprites.remove(s)

    def set_icons(self, icons):
        if len(icons) != len(self.sprites):
            self.reset_icon_count(len(icons))
        if self.sources != icons:
            self.sources = copy.copy(icons)
            for sprite, i in zip(self.sprites, icons):
                sprite.source = i
