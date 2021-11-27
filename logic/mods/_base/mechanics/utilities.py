import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from nutil.vars import normalize
from logic.mechanics.common import *


class Utilities:
    @classmethod
    def diminishing_curve(cls, value, spread=100, start_value=0):
        """
        Returns a value between 1 and 0 such that higher input values approach 0.
        Spread represents how slow to approach 0. Lower spread will result in
        approaching 0 faster, higher step will result in slower approach.
        In particular, spread is the input value that results in 0.5 (with 0 start value).
        Start value represents at what minimum value the result begins to drop from 1.
        """
        return spread / (spread + max(0, value-start_value))

    @classmethod
    def find_target(cls, api, uid, target_point,
            range=None, include_hitbox=True,
            draw_miss_vfx=True, mask=None, enemy_only=True, alive_only=True,
        ):
        pos = api.get_position(uid)
        if range is None:
            range = float('inf')
        mask_ = api.mask_enemies(uid) if enemy_only else np.ones(len(api.units))
        if mask is not None:
            mask_ = np.logical_and(mask_, mask)
        target_uid, dist = api.nearest_uid(target_point, mask=mask_, alive_only=alive_only)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        attack_pos = api.get_position(target_uid)
        attack_target = api.units[target_uid]
        total_range = range + api.get_stats(target_uid, STAT.HITBOX) if include_hitbox else range
        dist = math.dist(pos, attack_pos)
        if dist > total_range:
            if draw_miss_vfx and uid == 0:
                api.add_visual_effect(VisualEffect.LINE, 10, {
                    'p1': pos,
                    'p2': pos + normalize(attack_pos - pos, range),
                    'color': api.units[uid].color,
                })
            return FAIL_RESULT.OUT_OF_RANGE
        return target_uid

    @classmethod
    def find_target_enemy(cls, *args, **kwargs):
        return cls.find_target(*args, enemy_only=True, **kwargs)

    @classmethod
    def find_aoe_targets(cls, api, point, radius, mask=None, alive_only=True):
        dists = api.get_distances(point) - api.get_stats(slice(None), STAT.HITBOX)
        in_radius = dists < radius
        if mask is not None:
            in_radius = np.logical_and(in_radius, mask)
        if alive_only:
            in_radius = np.logical_and(in_radius, api.mask_alive())
        return in_radius
