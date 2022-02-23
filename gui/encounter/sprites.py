import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math, copy
import numpy as np
from nutil.vars import modify_color, minmax
from nutil.time import ratecounter
from nutil.kex import widgets
from gui import cc_int, center_position, center_sprite
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from data.settings import Settings
from logic.common import *


MIN_HITBOX_SCALE = 0.25


class Sprites(widgets.RelativeLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fog_size = Settings.get_setting('fog', 'UI')
        self.fog_color = str2color(Settings.get_setting('fog_color', 'UI'))
        self.fog_center = np.array([0, 0])
        self.fog_radius = 500
        self.set_units([], [], [])
        self.enc.interface.register('set_fog_center', self.set_fog_center)
        self.enc.interface.register('set_fog_radius', self.set_fog_radius)
        self.enc.interface.register('set_units', self.set_units)
        self.enc.interface.register('update_units', self.update_units)

    def set_fog_center(self, pos):
        self.__fog_center = pos

    def set_fog_radius(self, radius):
        self.__fog_radius = radius

    def set_units(self, sprites, topbar_colors, botbar_colors):
        self.clear_widgets()
        self.canvas.clear()
        if self.fog_size:
            with self.canvas.after:
                self.fog = widgets.Image(
                    source=Assets.get_sprite('ui.fog'),
                    color=self.fog_color,
                    allow_stretch=True)

        assert len(sprites) == len(topbar_colors) == len(botbar_colors)
        unit_count = len(sprites)
        self.visible_mask = self.last_visible = np.zeros(unit_count, dtype=np.bool)
        self.visible_count = 0
        self.sprites = []
        for sprite, topbar, botbar in zip(sprites, topbar_colors, botbar_colors):
            s = Sprite(source=sprite)
            s.bar1.fg, s.bar2.fg = topbar, botbar
            s.bar2.bg = (0, 0, 0, 0)
            self.sprites.append(s)

        self.unit_hitbox_radii = np.full(unit_count, 100)
        self.unit_positions = np.zeros((unit_count, 2))
        self.unit_top_statbars = np.zeros(unit_count)
        self.unit_bot_statbars = np.zeros(unit_count)

    def update_units(self, visible_mask, hitbox_radii, positions, top_bars, bot_bars, statuses_list):
        assert len(visible_mask) == len(self.sprites)
        # Categorize units by visibility
        self.visible_mask = visible_mask
        newly_visible = (self.visible_mask == True) & np.invert(self.last_visible)
        newly_invisible = (self.visible_mask == False) & self.last_visible
        self.last_visible = self.visible_mask
        self.visible_count = self.visible_mask.sum()
        # Add/remove sprites from canvas
        for uid in np.flatnonzero(newly_invisible):
            self.canvas.remove(self.sprites[uid])
        for uid in np.flatnonzero(newly_visible):
            self.canvas.add(self.sprites[uid])
        # Update the visible sprites
        assert len(hitbox_radii) == self.visible_count
        assert len(positions) == self.visible_count
        assert len(top_bars) == self.visible_count
        assert len(bot_bars) == self.visible_count
        assert len(statuses_list) == self.visible_count
        self.unit_hitbox_radii[self.visible_mask] = hitbox_radii
        self.unit_positions[self.visible_mask] = positions
        for i, uid in enumerate(np.flatnonzero(self.visible_mask)):
            s = self.sprites[uid]
            s.bar1.progress = top_bars[i]
            s.bar2.progress = bot_bars[i]
            s.set_icons(statuses_list[i])

    def update(self):
        # Fog
        if self.fog_size:
            pixel_size = int(self.fog_size * self.__fog_radius / self.enc.upp)
            self.fog.size = (pixel_size, pixel_size)
            fog_pos = self.enc.real2pix(self.__fog_center)
            self.fog.pos = center_sprite(fog_pos, self.fog.size)

        # Sprites
        if self.visible_count == 0:
            return

        logger.debug(f'Drawing {self.visible_count} sprites: {np.flatnonzero(self.visible_mask)}')
        # Convert all real values to pixel values
        hp_height = max(5, 10 / self.enc.upp)
        subset_pos = self.enc.real2pix(self.unit_positions[self.visible_mask])
        subset_hb = self.unit_hitbox_radii[self.visible_mask] * 2 / min(self.enc.upp, (1/MIN_HITBOX_SCALE))

        for i, uid in enumerate(np.flatnonzero(self.visible_mask)):
            with ratecounter(self.enc.timers['sprite_single']):
                s = self.sprites[uid]
                s.size = subset_hb[i], subset_hb[i]
                s.pos = subset_pos[i]

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
        self._fg_rect.size = self._size[0]*minmax(0, 1, self._progress), self._size[1]

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, x):
        self._progress = x
        self._fg_rect.size = self._size[0]*minmax(0, 1, self._progress), self._size[1]

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
