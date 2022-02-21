import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
import math
from nutil.vars import is_floatable
from nutil.kex import widgets
from nutil.time import ratecounter
from gui.encounter import EncounterViewComponent
from gui import center_position, cc_int
from data.settings import Settings
from data.assets import Assets
from engine import VFX as VFXEnum


class VFX(widgets.RelativeLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__cached_vfx = []
        self.__draw_types = {
            VFXEnum.BACKGROUND: self.draw_background,
            VFXEnum.LINE: self.draw_line,
            VFXEnum.CIRCLE: self.draw_circle,
            VFXEnum.QUAD: self.draw_quad,
            VFXEnum.SPRITE: self.draw_sprite,
        }
        self.enc.interface.register('set_vfx', self.set_vfx)

    @property
    def vfx_count(self):
        return len(self.__cached_vfx)

    def set_vfx(self, vfx_list):
        self.__cached_vfx = vfx_list

    def update(self):
        self.canvas.clear()
        for effect in self.__cached_vfx:
            with ratecounter(self.enc.timers['vfx_single']):
                draw_call = self.__draw_types[effect.eid]
                draw_call(effect)
                with self.canvas:
                    widgets.kvColor(1,1,1,1)

    def draw_background(self, effect):
        color = (1, 0, 0, 0.15)
        if 'color' in effect.params:
            color = effect.params['color']
        if 'fade' in effect.params:
            if len(color) == 4: a = color[3]
            else: a = 1
            a *= 1-(max(0.0001, effect.elapsed_ticks) / effect.params['fade'])
            color = (*color[:3], a)
        with self.canvas:
            widgets.kvColor(*color)
            widgets.kvRectangle(pos=self.to_local(*self.pos), size=self.size)

    def draw_line(self, effect):
        width = 2
        if 'width' in effect.params:
            width = effect.params['width']
        color = (0, 0, 0)
        if 'color' in effect.params:
            color = effect.params['color']
        points = (*self.enc.real2pix(effect.params['p1']),
                  *self.enc.real2pix(effect.params['p2']))
        with self.canvas:
            widgets.kvColor(*color)
            widgets.kvLine(points=points, width=width)

    def draw_circle(self, effect):
        color = (0, 0, 0)
        if 'color' in effect.params:
            color = effect.params['color']
        if 'fade' in effect.params:
            if len(color) == 4: a = color[3]
            else: a = 1
            a *= 1-(max(0.0001, effect.elapsed_ticks) / effect.params['fade'])
            color = (*color[:3], a)
        if 'center' in effect.params:
            point = self.enc.real2pix(effect.params['center'])
        elif 'uid' in effect.params:
            point = self.enc.real2pix(self.api.engine.get_position(effect.params['uid']))
        else:
            raise ValueError(f'Missing center/uid for drawing circle vfx')
        radius = effect.params['radius'] / self.enc.upp
        pos = np.array(point) - radius
        size = radius*2, radius*2
        with self.canvas:
            widgets.kvColor(*color)
            widgets.kvEllipse(pos=cc_int(pos), size=cc_int(size))

    def draw_quad(self, effect):
        color = (0, 0, 0)
        if 'color' in effect.params:
            color = effect.params['color']
        if 'fade' in effect.params:
            if len(color) == 4: a = color[3]
            else: a = 1
            a *= 1-(max(0.0001, effect.elapsed_ticks) / effect.params['fade'])
            color = (*color[:3], a)
        real_points = effect.params['points']
        pix_coords = tuple(self.enc.real2pix(_) for _ in real_points)
        points = tuple(int(_) for _ in np.array(pix_coords).flatten())
        with self.canvas:
            widgets.kvColor(*color)
            widgets.kvQuad(points=points)

    def draw_sprite(self, effect):
        with ratecounter(self.enc.timers['vfx_sprite_single']):
            size = np.array([100, 100]) / self.enc.upp
            color = (1, 1, 1)
            sprite_source = effect.params['source']

            if 'size' in effect.params:
                size = np.array(effect.params['size']) / self.enc.upp

            if 'color' in effect.params:
                color = effect.params['color']

            if 'fade' in effect.params:
                if len(color) == 4:
                    a = color[3]
                else:
                    a = 1
                a *= 1 - (max(0.0001, effect.elapsed_ticks) / effect.params['fade'])
                color = (*color[:3], a)

            if 'point' in effect.params:
                point = cc_int(self.enc.real2pix(effect.params['point']))
            elif 'uid' in effect.params:
                uid =  effect.params['uid']
                point = cc_int(self.enc.real2pix(self.api.engine.get_position(uid)))
            else:
                raise ValueError(f'Missing point/uid for drawing sprite vfx')

            with self.canvas:
                widgets.kvColor(*color)
                widgets.kvRectangle(
                    pos=center_position(point, size),
                    size=size,
                    source=sprite_source,
                    allow_strech=True,
                )
