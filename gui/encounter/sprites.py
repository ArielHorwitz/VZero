import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


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
        # Redraw must be called before any other method
        self.redraw()

    def redraw(self):
        self.cached_sprites = []
        self.cached_hpbars = []
        self.last_visible = np.zeros(len(self.api.units), dtype=np.int)
        self.clear_widgets()
        self.canvas.clear()
        for unit in self.api.units:
            # Sprite
            sprite = widgets.kvRectangle(source=unit.sprite)
            self.cached_sprites.append(sprite)
            # HP bar
            igroup = widgets.kvInstructionGroup()
            self.cached_hpbars.append(igroup)

    def update(self):
        visibles = self.api.get_visible_uids(view_size=self.enc.view_size)
        newly_visible = np.logical_and(visibles == True, np.invert(self.last_visible))
        newly_invisible = np.logical_and(visibles == False, self.last_visible)
        self.last_visible = visibles
        self.drawn_count = visibles.sum()

        all_pos = self.enc.real2pix(self.api.get_all_positions())
        hps, max_hps = self.api.get_sprite_bars()
        hp_height = max(5, 10 / self.enc.upp)
        hitboxes = np.array(self.api.get_sprite_size()) * 2 / min(self.enc.upp, (1/MIN_HITBOX_SCALE))

        for uid in np.argwhere(newly_visible):
            uid = uid[0] # np.argwhere returns some nd-shape
            logger.debug(f'Entering draw range: {uid}')
            self.canvas.add(self.cached_sprites[uid])
            self.canvas.add(self.cached_hpbars[uid])

        for uid in np.argwhere(newly_invisible):
            uid = uid[0] # np.argwhere returns some nd-shape
            logger.debug(f'Leaving draw range: {uid}')
            self.canvas.remove(self.cached_sprites[uid])
            self.canvas.remove(self.cached_hpbars[uid])

        for uid in np.argwhere(visibles):
            with ratecounter(self.enc.timers['sprite_single']):
                uid = uid[0] # np.argwhere returns some nd-shape
                # Sprite
                size = cc_int((hitboxes[uid], hitboxes[uid]))
                pos = center_position(all_pos[uid], size)
                self.cached_sprites[uid].size = size
                self.cached_sprites[uid].pos = pos
                # HP bar
                igroup = self.cached_hpbars[uid]
                if hps[uid] > 0 and not self.enc.map_mode:
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
