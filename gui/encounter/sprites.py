import numpy as np

from nutil.time import ratecounter
from nutil.kex import widgets
from gui import cc_int, center_position
from gui.encounter import EncounterViewComponent
from data.load import Assets
from logic.mechanics.common import *


class Sprites(widgets.RelativeLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.drawn_count = 0
        # Redraw must be called before any other method
        self.redraw()

    def redraw(self):
        self.cached_sprites = []
        self.cached_hpbars = []
        self.last_visible = np.zeros(self.api.unit_count, dtype=np.int)
        self.clear_widgets()
        self.canvas.clear()
        for unit in self.api.units:
            # Sprite
            sprite_source = Assets.get_sprite('unit', unit.sprite)
            sprite = widgets.kvRectangle(source=sprite_source)
            self.cached_sprites.append(sprite)
            # HP bar
            igroup = widgets.kvInstructionGroup()
            self.cached_hpbars.append(igroup)

    def update(self):
        max_los = max(np.array(self.size)) * self.enc.upp
        visibles = self.api.get_distances(self.api.get_position(0)) <= max_los
        newly_visible = np.logical_and(visibles == True, np.invert(self.last_visible))
        newly_invisible = np.logical_and(visibles == False, self.last_visible)
        self.last_visible = visibles
        self.drawn_count = visibles.sum()

        all_pos = self.enc.real2pix(self.api.get_position())
        max_hps = self.api.get_stats(slice(None), STAT.HP, value_name=VALUE.MAX_VALUE)
        hps = self.api.get_stats(slice(None), STAT.HP) / max_hps
        hp_height = max(3, 5 / self.enc.upp)
        hitboxes = self.api.get_stats(slice(None), STAT.HITBOX) * 2 / self.enc.upp
        hitboxes[hitboxes<30] = 30

        for uid in np.argwhere(newly_visible):
            uid = uid[0] # np.argwhere returns some nd-shape
            self.canvas.add(self.cached_sprites[uid])
            self.canvas.add(self.cached_hpbars[uid])

        for uid in np.argwhere(newly_invisible):
            uid = uid[0] # np.argwhere returns some nd-shape
            self.canvas.remove(self.cached_sprites[uid])
            self.canvas.remove(self.cached_hpbars[uid])

        for uid in np.argwhere(visibles):
            uid = uid[0] # np.argwhere returns some nd-shape
            # Sprite
            size = cc_int((hitboxes[uid], hitboxes[uid]))
            pos = center_position(all_pos[uid], size)
            self.cached_sprites[uid].size = size
            self.cached_sprites[uid].pos = pos
            # HP bar
            igroup = self.cached_hpbars[uid]
            if hps[uid] > 0 and self.enc.upp < 1.5:
                if igroup not in self.canvas.children:
                    self.canvas.add(igroup)
                igroup.clear()
                size = cc_int((hitboxes[uid]*2, hp_height))
                pos = center_position(all_pos[uid] + (0, hitboxes[uid]/2), size)
                self.draw_hp_bar(igroup, pos, size, hps[uid])

            else:
                self.canvas.remove(igroup)

    def draw_hp_bar(self, igroup, pos, size, hp):
        igroup.add(widgets.kvColor(0, 0, 0))
        igroup.add(widgets.kvRectangle(pos=pos, size=size))
        igroup.add(widgets.kvColor(1, 0, 0))
        hp_size = size[0]*hp, size[1]
        igroup.add(widgets.kvRectangle(pos=pos, size=hp_size))
        igroup.add(widgets.kvColor(1, 1, 1))