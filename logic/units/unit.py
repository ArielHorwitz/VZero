
import math
import numpy as np
from logic.mechanics.common import *


DEFAULT_HITBOX = 20


class Unit:
    def __init__(self, api, uid, allegience,
                 name=None, hitbox=DEFAULT_HITBOX,
                 internal_name=None, params=None,
                 ):
        self.__uid = uid
        self.__internal_name = internal_name
        self.name = 'Unnamed unit' if name is None else name
        self.hitbox = hitbox
        self.allegience = allegience
        self.color_code = 1
        self.setup(api, **params)

    def setup(self, api, **params):
        pass

    def poll_abilities(self, api):
        return None

    @property
    def uid(self):
        return self.__uid

    @property
    def internal_name(self):
        return self.__internal_name

    @property
    def sprite(self):
        return self.internal_name + '.png'

    @property
    def debug_str(self):
        return f'{self} debug str undefined.'


class Player(Unit):
    def setup(self, api, **params):
        self.color_code = 0
        self.preferred_target = None
        self.last_attack = api.tick - 100
        self.targeting_rate = 10

    def set_preferred_target(self, api, target):
        enemies = api.mask_enemies(self.uid)
        nearest = api.nearest_uid(target, mask=enemies)[0]
        self.preferred_target = nearest
        print(f'Set attack target: {self.preferred_target}')
        return nearest is not None

    def poll_abilities(self, api):
        if api.tick < self.last_attack + self.targeting_rate:
            return None
        self.last_attack = api.tick
        pos = api.get_position()
        my_pos = pos[self.uid]
        # Unset if target is dead
        if self.preferred_target is not None:
            if api.get_stats(self.preferred_target, STAT.HP) <= 0:
                self.preferred_target = None
        # Try to reset if target not set
        if self.preferred_target is None:
            if not self.set_preferred_target(api, my_pos):
                return None
        # We have a target, check range
        target_pos = pos[self.preferred_target]
        hitbox = api.units[self.preferred_target].hitbox
        range = api.get_stats(self.uid, STAT.RANGE)
        if math.dist(my_pos, target_pos) > range + hitbox:
            return None
        return [(ABILITIES.ATTACK, target_pos)]

    @property
    def debug_str(self):
        return f'target uid: {self.preferred_target}.'


UNIT_TYPES = {
    'player': Player,
}
