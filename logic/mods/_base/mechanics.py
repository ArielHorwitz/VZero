import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from logic.mechanics.common import *
from nutil.vars import normalize


class Mechanics:
    @classmethod
    def apply_loot(cls, api, uid, target, range):
        pos = api.get_position(uid)
        # Check
        mask_gold = 0 < api.get_stats(index=slice(None), stat=STAT.GOLD)
        lootables = np.logical_and(api.mask_dead(), mask_gold)
        loot_target, dist = api.nearest_uid(pos, mask=lootables, alive_only=False)
        if loot_target is None:
            return FAIL_RESULT.MISSING_TARGET, None
        loot_pos = api.get_position(loot_target)
        if math.dist(pos, loot_pos) > range:
            return FAIL_RESULT.OUT_OF_RANGE, None
        # Apply and move remains
        looted_gold = api.get_stats(loot_target, STAT.GOLD)
        api.set_stats(loot_target, STAT.GOLD, 0)
        api.set_stats(loot_target, (STAT.POS_X, STAT.POS_Y), (-1_000_000, -1_000_000))
        logger.debug(f'{api.units[uid].name} removed {looted_gold} gold from {api.units[loot_target].name}')
        return looted_gold, loot_pos

    @staticmethod
    def apply_move(api, uid, target=None, move_speed=None):
        if move_speed is None:
            move_speed = api.get_velocity(uid)
            logger.debug(f'apply_move using current move speed: {move_speed}')
        slow = api.get_status(uid, STATUS.SLOW)
        if slow > 0:
            move_speed *= max(0, 1 - slow)
        move_speed /= 100
        if target is None:
            target = api.get_position(uid, value_name=VALUE.TARGET_VALUE)
        current_pos = api.get_position(uid)
        target_vector = target - current_pos
        delta = normalize(target_vector, move_speed)
        api.set_position(uid, delta, value_name=VALUE.DELTA)
        api.set_position(uid, target, value_name=VALUE.TARGET_VALUE)

    @classmethod
    def apply_debuff(cls, api, uid, status, duration, stacks):
        logger.debug(f'Applied status {status.name} {duration} × {stacks} to {api.units[uid].name}')
        api.set_status(uid, status, duration, stacks)

    @classmethod
    def do_brute_damage(cls, api, source_uid, targets_mask, damage):
        source = api.units[source_uid]
        if not isinstance(targets_mask, np.ndarray):
            uid = targets_mask
            targets_mask = np.full(api.unit_count, False)
            targets_mask[uid] = 1
        # Stop if no targets
        if targets_mask.sum() == 0:
            logger.debug(f'{source.name} wished to apply {damage:.2f} brute damage but no targets in mask')
            return

        logger.debug(f'{source.name} applying {damage:.2f} brute damage to {targets_mask.nonzero()[0]}')
        damages = targets_mask * damage
        damages = damages[targets_mask] - api.get_status(targets_mask, STATUS.ARMOR)
        damages[damages < 0] = 0

        cls.do_pure_damage(api, targets_mask, damages)

    @classmethod
    def do_pure_damage(cls, api, targets_mask, damages):
        api.set_stats(targets_mask, STAT.HP, -damages, additive=True)
        # Play ouch feedback if player uid is in targets
        if targets_mask[0] > 0:
            api.add_visual_effect(VisualEffect.BACKGROUND, 40)
            api.add_visual_effect(VisualEffect.SFX, 1, params={'sfx': 'ouch', 'category': 'ui', 'volume': 'feedback'})
        # Check if non player is in list
        if targets_mask.sum() - targets_mask[0] > 0:
            api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'hit', 'category': 'ui', 'volume': 'feedback'})
        if targets_mask.sum() > 1:
            logger.debug(f'{targets_mask.nonzero()[0]} took {damages} pure damage.')
        if targets_mask.sum() == 1:
            logger.debug(f'{api.units[targets_mask.nonzero()[0][0]].name} took {damages} pure damage.')

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
            return None
        attack_pos = api.get_position(target_uid)
        attack_target = api.units[target_uid]
        if include_hitbox:
            range += api.get_stats(target_uid, STAT.HITBOX)
        dist = math.dist(pos, attack_pos)
        if dist > range:
            if draw_miss_vfx and uid == 0:
                api.add_visual_effect(VisualEffect.LINE, 10, {
                    'p1': pos,
                    'p2': pos + normalize(attack_pos - pos, range),
                    'color': api.units[uid].color,
                })
            return None
        logger.debug(f'find_target: {pos} {range} {target_point} {target_uid} {dist}')
        return target_uid

    @classmethod
    def find_target_enemy(cls, *args, **kwargs):
        return cls.find_target(*args, enemy_only=True, **kwargs)

    @classmethod
    def get_aoe_targets(cls, api, point, radius, mask=None):
        dists = api.get_distances(point) - api.get_stats(slice(None), STAT.HITBOX)
        in_radius = dists < radius
        if mask is not None:
            in_radius = np.logical_and(in_radius, mask)
        return in_radius
