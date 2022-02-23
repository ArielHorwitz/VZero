import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
from collections import defaultdict
import numpy as np
from nutil.vars import normalize, modify_color
from data.assets import Assets
from logic.common import *


MAX_MOVESPEED = 500


class Mechanics:
    STATUS_SKIP_LOGGING = {STATUS.SHOP, STATUS.FOUNTAIN}
    STATUS_SKIP_SENSITIVITY = {STATUS.STOCKS, STATUS.SHOP, STATUS.SENSITIVITY}
    STATUS_DURATION_SENSITIVITY = {STATUS.BOUNDED}

    @classmethod
    def apply_loot(cls, api, uid, target, range):
        pos = api.get_position(uid)
        # Check
        loot_target, dist = api.nearest_uid(pos, mask=api.mask_dead(), alive_only=False)
        if loot_target is None:
            return FAIL_RESULT.MISSING_TARGET, None
        if api.unit_distance(uid, loot_target) > range:
            return FAIL_RESULT.MISSING_TARGET, None
        loot_pos = api.get_position(loot_target)
        # Apply and move remains
        looted_gold = api.get_stats(loot_target, STAT.GOLD)
        api.set_stats(loot_target, STAT.GOLD, 0)
        api.set_stats(loot_target, (STAT.POS_X, STAT.POS_Y), (-1_000_000, -1_000_000))
        api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
        Assets.play_sfx('ui.loot', volume='sfx')
        logger.debug(f'{api.units[uid]} looted {looted_gold} gold from {api.units[loot_target]}.')
        return loot_pos, looted_gold

    @classmethod
    def apply_teleport(cls, api, uid, target, reset_target=False):
        bounded = cls.get_status(api, uid, STAT.BOUNDED)
        if bounded > 0:
            target = api.get_position(uid)
        api.set_position(uid, target)
        if reset_target:
            api.set_position(uid, target, VALUE.TARGET)
        else:
            api.align_to_target(uid)

    @classmethod
    def apply_walk(cls, api, mask, target=None):
        mask = mask & cls.moveable(api)
        if mask.sum() == 0:
            return
        if target is None:
            target = api.get_positions(mask, value_name=VALUE.TARGET)
        speed = cls.get_movespeed(api, mask)
        api.set_move(mask, target, speed)

    @classmethod
    def halt_move(cls, api, mask):
        pos = api.get_positions(mask)
        api.set_positions(mask, 0, value_name=VALUE.DELTA)
        api.set_positions(mask, pos, value_name=VALUE.TARGET)

    @classmethod
    def apply_debuff(cls, api, targets, status,
        duration=None, stacks=None, duration_add=0, stacks_add=0,
        caster=None, reset_move=True, apply_sensitivity=True):
        if targets.sum() == 0:
            return

        dur_sens = stacks_sens = 1
        if status not in cls.STATUS_SKIP_SENSITIVITY:
            if status in cls.STATUS_DURATION_SENSITIVITY:
                dur_sens = cls._combined_sensitivity(api, caster, targets)
            else:
                stacks_sens = cls._combined_sensitivity(api, caster, targets)

        if duration is None:
            duration = api.get_status(targets, status, value_name=STATUS_VALUE.DURATION)
            duration = np.atleast_1d(duration)
            duration[duration < 0] = 0
        else:
            duration *= dur_sens
        if stacks is None:
            stacks = api.get_status(targets, status)
        else:
            stacks *= stacks_sens

        duration += duration_add * dur_sens
        stacks += stacks_add * stacks_sens

        if status not in cls.STATUS_SKIP_LOGGING:
            logger.debug(f'Applying status {status.name} {duration} × {stacks} to targets: {np.flatnonzero(targets)}.')

        api.set_status(targets, status, duration, stacks)

        if status is STATUS.BOUNDED and reset_move:
            cls.halt_move(api, cls.mask(api, targets))
        if status is STATUS.SLOW and reset_move:
            cls.apply_walk(api, cls.mask(api, targets))

    @classmethod
    def _combined_sensitivity(cls, api, caster, targets):
        sensitivity = cls.get_status(api, targets, STAT.SENSITIVITY)
        if caster is not None:
            sensitivity += cls.get_status(api, caster, STAT.SENSITIVITY)
        sensitivity = cls.scaling(sensitivity, ascending=True)
        return 1 + sensitivity

    @classmethod
    def apply_regen(cls, api, targets, stat, duration, delta):
        # logger.debug(f'Applying {delta} {stat.name} regen for {duration} ticks to {np.flatnonzero(targets)}')
        api.add_dmod(duration, targets, stat, delta)

    @classmethod
    def do_normal_damage(cls, api, source_uid, targets_mask, damage):
        # Stop if no targets
        if targets_mask.sum() == 0:
            return
        logger.debug(f'{source_uid} applying {damage:.2f} normal damage to {np.flatnonzero(targets_mask)}.')
        all_damage = targets_mask * damage

        # Cuts add flat damage
        all_damage[targets_mask] += cls.get_status(api, targets_mask, STAT.CUTS)

        # Armor reduction
        armor = cls.get_status(api, targets_mask, STAT.ARMOR)
        all_damage[targets_mask] *= cls.scaling(armor)

        # Converted pure damage
        cls.do_pure_damage(api, all_damage)

        # Spikes return pure damage
        spike_damage = cls.get_status(api, targets_mask, STAT.SPIKES).sum()
        cls.do_pure_damage(api, cls.mask(api, source_uid) * spike_damage)

        # Lifesteal
        lifesteal = cls.get_status(api, source_uid, STAT.LIFESTEAL) / 100
        cls.do_heal(api, cls.mask(api, source_uid), lifesteal * sum(all_damage))

    @classmethod
    def do_blast_damage(cls, api, source_uid, targets_mask, damage):
        # Stop if no targets
        if targets_mask.sum() == 0:
            return
        logger.debug(f'{source_uid} applying {damage:.2f} blast damage to {np.flatnonzero(targets_mask)}.')
        all_damage = targets_mask * damage

        # Vanity amplification
        vanity = cls.get_status(api, targets_mask, STAT.VANITY) / 100
        all_damage[targets_mask] *= 1 + vanity

        # Converted pure damage
        cls.do_pure_damage(api, all_damage)

        # Reflect pure damage
        reflect = cls.get_status(api, targets_mask, STAT.REFLECT) / 100
        reflected = sum(all_damage[targets_mask] * reflect)
        cls.do_pure_damage(api, cls.mask(api, source_uid) * reflected)

    @classmethod
    def do_pure_damage(cls, api, damages):
        if damages.sum() == 0:
            return
        damages[damages<0] = 0
        api.set_stats(slice(None), STAT.HP, -damages, additive=True)
        took_damage = np.flatnonzero(damages)
        logger.debug(f'{took_damage} took {damages[damages > 0]} pure damage.')
        api.logic.ouch(took_damage)

    @classmethod
    def do_heal(cls, api, targets_mask, heal):
        if isinstance(heal, np.ndarray):
            heal[heal<0] = 0
        elif heal < 0:
            heal = 0
        api.set_stats(targets_mask, STAT.HP, heal, additive=True)
        logger.debug(f'{targets_mask.nonzero()[0]} received {heal} healing.')

    # Utilities
    @classmethod
    def moveable(cls, api):
        unbounded = cls.get_status(api, slice(None), STAT.BOUNDED) == 0
        normal_weight = api.get_stats(slice(None), STAT.WEIGHT) >= 0
        return unbounded & normal_weight

    @classmethod
    def unmoveable(cls, api):
        return np.invert(cls.moveable(api))

    @classmethod
    def get_movespeed(cls, api, mask):
        if not isinstance(mask, np.ndarray):
            mask = cls.mask(api, mask)
        speed = MAX_MOVESPEED * cls.scaling(cls.get_status(api, mask, STAT.MOVESPEED), ascending=True)
        speed *= ticks2s()
        slow = cls.get_status(api, mask, STAT.SLOW)
        speed[slow > 0] *= cls.scaling(slow[slow > 0])
        return speed

    @classmethod
    def mask(cls, api, targets=None):
        a = np.zeros(api.unit_count, dtype=np.bool)
        if targets is not None:
            a[targets] = True
        return a

    @staticmethod
    def rp2reduction(rp):
        return 50 / (50 + rp)

    @staticmethod
    def scaling(sp, curve=50, ascending=False):
        if not ascending:
            return np.array(curve) / (np.array(curve) + sp)
        return np.array(1) - (np.array(curve) / (np.array(curve) + sp))

    @classmethod
    def get_status(cls, api, uid, stat):
        base = api.get_stats(uid, stat)
        from_status = api.get_status(uid, STAT2STATUS[stat])
        return base + from_status

    @classmethod
    def get_stats(cls, api, uid, stat):
        base = api.get_stats(uid, stat)
        if stat in STAT2STATUS:
            base += api.get_status(uid, STAT2STATUS[stat])
        return base

    @staticmethod
    def bound_to_map(api, point):
        point = np.array(point)
        map_size = np.array(api.map_size)
        point[point < 0] = 0
        over = point > map_size
        point[over] = map_size[over]
        return point


class Rect:
    @classmethod
    def from_point(cls, origin, target, width, height, offset=0):
        direction_vector = target - origin
        if direction_vector.sum() == 0:
            direction_vector = [10, 10]
        center_offset = normalize(direction_vector, height/2+offset+0.001)
        rect_center = origin + center_offset
        rotation = cls.find_vector_angle_radians(direction_vector)
        return cls(rect_center, rotation, width, height)

    def __init__(self, center, rotation, width, height):
        self.center = center
        self.rotation = rotation
        self.width = width
        self.height = height
        self.point_vectors = np.array([
            [-width/2, -height/2],  # bl
            [width/2, -height/2],  # br
            [width/2, height/2],  # tr
            [-width/2, height/2],  # tl
        ])
        self.__rotated_points = self.rotated_points(rotation)

    def check_colliding_circles(self, p, circle_radius):
        rx, ry = self.center
        x, y = p[:, 0], p[:, 1]
        # Rotate center of circle based on our rotation (makes for easier calc)
        mc = math.cos(self.rotation)
        ms = math.sin(self.rotation)
        cx = (x - rx) * mc - (y - ry) * ms + self.width / 2
        cy = (x - rx) * ms + (y - ry) * mc + self.height / 2
        # Find the closest x point from center of circle
        near_x = cx.copy()
        near_x[cx < 0] = 0
        near_x[cx > self.width] = self.width
        # Find the closest y point from center of circle
        near_y = cy.copy()
        near_y[cy < 0] = 0
        near_y[cy > self.height] = self.height
        # Find distance from circle center to nearest point in the rectangle
        p_ = np.stack((cx, cy), axis=1)
        nearest = np.stack((near_x, near_y), axis=1)
        distance_to_nearest = np.linalg.norm((p_ - nearest), axis=1)
        # Consider the circle's radius
        return distance_to_nearest < circle_radius

    @property
    def points(self):
        return self.__rotated_points

    @classmethod
    def find_vector_angle_radians(cls, direction_vector):
        base = np.array([0.0, 1.0])
        neg_x = direction_vector[0] < 0
        v1u = direction_vector / np.linalg.norm(direction_vector)
        v2u = base / np.linalg.norm(base)
        radians = np.arccos(np.clip(np.dot(v1u, v2u), -1.0, 1.0))
        radians *= -1 if neg_x else 1
        return radians

    def rotated_points(self, radians=0):
        if radians == 0:
            return self.point_vectors
        c, s = np.cos(radians), np.sin(radians)
        j = np.matrix([[c, s], [-s, c]])
        rotated_point_vectors = np.vstack([np.hstack(np.dot(j, p).T) for p in self.point_vectors])
        return rotated_point_vectors + self.center
