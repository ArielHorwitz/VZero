import numpy as np
import math
from nutil.vars import is_floatable
from nutil.kex import widgets
from nutil.time import ratecounter
from gui.encounter import EncounterViewComponent
from gui import center_position, cc_int
from data.load import Settings, Assets


class VFX(widgets.RelativeLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__cached_vfx = []

    def update(self):
        # Clear
        for instruction in self.__cached_vfx:
            if isinstance(instruction,widgets.Image):
                instruction.canvas.clear()
                del instruction
            else:
                self.canvas.remove(instruction)
        self.__cached_vfx = []

        # VFX
        for effect in self.api.get_visual_effects():
            with ratecounter(self.enc.timers['vfx_single']):
                # Flash background
                if effect.eid is effect.BACKGROUND:
                    color = (1, 0, 0, 0.15)
                    if 'color' in effect.params:
                        color = effect.params['color']
                    with self.canvas:
                        self.__cached_vfx.append(widgets.kvColor(*color))
                        self.__cached_vfx.append(widgets.kvRectangle(pos=self.to_local(*self.pos), size=self.size))

                # Draw line
                if effect.eid is effect.LINE:
                    width = 2
                    if 'width' in effect.params:
                        width = effect.params['width']
                    color = (0, 0, 0)
                    if 'color' in effect.params:
                        color = effect.params['color']
                    points = (*self.enc.real2pix(effect.params['p1']),
                              *self.enc.real2pix(effect.params['p2']))
                    with self.canvas:
                        self.__cached_vfx.append(widgets.kvColor(*color))
                        self.__cached_vfx.append(widgets.kvLine(points=points, width=width))

                # Draw circle
                if effect.eid is effect.CIRCLE:
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
                        point = self.enc.real2pix(self.api.get_position(effect.params['uid']))
                    else:
                        raise ValueError(f'Missing center/uid for drawing circle vfx')
                    radius = effect.params['radius'] / self.enc.upp
                    pos = np.array(point) - radius
                    size = radius*2, radius*2
                    with self.canvas:
                        self.__cached_vfx.append(widgets.kvColor(*color))
                        self.__cached_vfx.append(widgets.kvEllipse(pos=cc_int(pos), size=cc_int(size)))

                # Draw Sprite
                if effect.eid is effect.SPRITE:
                    with ratecounter(self.enc.timers['vfx_sprite_single']):
                        size = None
                        tint = (1, 1, 1)
                        angle = 0
                        offset = (0, 0)
                        scale = (1,1)
                        sprite_name = Assets.get_sprite('ability', effect.params['source'])

                        if 'tint' in effect.params:
                            tint = effect.params['tint']

                        if 'fade' in effect.params:
                            if len(tint) == 4:
                                a = tint[3]
                            else:
                                a = 1
                            a *= 1 - (max(0.0001, effect.elapsed_ticks) / effect.params['fade'])
                            tint = (*tint[:3], a)

                        if 'angle' in effect.params:
                            angle = effect.params['angle']

                        if 'offset' in effect.params:
                            offset = effect.params['offset']

                        if 'scale' in effect.params:
                            scale = effect.params['scale']

                        if 'size' in effect.params:
                            size = effect.params['size']

                        if 'stretch' in effect.params:
                            point = cc_int(self.enc.real2pix(effect.params['stretch'][0]))
                            dest = cc_int(self.enc.real2pix(effect.params['stretch'][1]))
                            angle += calc_angle(point, dest)
                        elif 'point' in effect.params:
                            point = cc_int(self.enc.real2pix(effect.params['point']))
                        elif 'uid' in effect.params:
                            uid =  effect.params['uid']
                            point = cc_int(self.enc.real2pix(self.api.get_position(uid)))
                        else:
                            raise ValueError(f'Missing point/stretch/uid for drawing sprite vfx')

                        with self.canvas:
                            self.__cached_vfx.append(widgets.kvRotate(angle=angle, axis=(0, 0, 1), origin=point))
                            sprite = widgets.Image(source=sprite_name,
                                                   color=tint,
                                                   allow_stretch=True,
                                                   keep_ratio=False)
                            if 'stretch' in effect.params:
                                new_pos, new_size = calc_image_line(point, dest, sprite.size)
                                sprite.size = new_size
                            elif 'point' in effect.params:
                                new_pos = point
                            elif 'uid' in effect.params:
                                new_pos = tuple((np.array(point) + (np.array(offset))))

                            new_size = cc_int(tuple(np.array(scale) * (sprite.size if size is None else size)))

                            sprite.pos = center_position(new_pos, new_size)
                            sprite.size = new_size
                            self.__cached_vfx.append(widgets.kvRotate(angle=-angle, axis=(0, 0, 1), origin=point))
                            self.__cached_vfx.append(sprite)

                # SFX
                if effect.eid is effect.SFX and self.api.e.auto_tick:
                    category = 'ability'
                    if 'category' in effect.params:
                        category = effect.params['category']
                    volume = 'sfx'
                    if 'volume' in effect.params:
                        volume = effect.params['volume']
                    Assets.play_sfx(
                        category, effect.params['sfx'],
                        volume=Settings.get_volume(volume),
                        allow_exception=False)


def calc_image_line(p1,p2,img_size):
    x1, y1 = p1
    x2, y2 = p2
    dis = math.dist(p1, p2)

    new_size = cc_int((dis, img_size[1]))
    new_pos = cc_int((x1,y1-(new_size[1]//2)))

    return new_pos, new_size


def calc_angle(p1,p2):
    x1, y1 = p1
    x2, y2, = p2
    sign = 0 if (x2-x1) >= 0 else 180
    dx = (x2-x1)
    dy = (y2-y1)
    if dx != 0:
        angle = math.degrees(math.atan(dy/dx))
    else:
        angle = 90

    return angle + sign
