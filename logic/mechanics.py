import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
import numpy as np
from nutil.vars import normalize
from engine.common import *


class Mechanics:
    STATUSES = {
        STAT.ARMOR: STATUS.ARMOR,
        STAT.LIFESTEAL: STATUS.LIFESTEAL,
        STAT.SPIKES: STATUS.SPIKES,
        STAT.VANITY: STATUS.VANITY,
    }
    STATUS_COLORS = {
        STATUS.ARMOR: COLOR.BLUE,
        STATUS.LIFESTEAL: COLOR.PINK,
        STATUS.SPIKES: COLOR.BLACK,
        STATUS.VANITY: COLOR.CYAN,
        STATUS.SLOW: COLOR.BROWN,
    }

    @classmethod
    def apply_loot(cls, api, uid, target, range):
        pos = api.get_position(uid)
        # Check
        mask_gold = 0 < api.get_stats(index=slice(None), stat=STAT.GOLD)
        lootables = np.logical_and(api.mask_dead(), mask_gold)
        loot_target, dist = api.nearest_uid(pos, mask=lootables, alive_only=False)
        if loot_target is None:
            return FAIL_RESULT.MISSING_TARGET, None, None
        loot_pos = api.get_position(loot_target)
        if math.dist(pos, loot_pos) > range:
            return FAIL_RESULT.OUT_OF_RANGE, None, None
        # Apply and move remains
        looted_gold = api.get_stats(loot_target, STAT.GOLD)
        api.set_stats(loot_target, STAT.GOLD, 0)
        api.set_stats(loot_target, (STAT.POS_X, STAT.POS_Y), (-1_000_000, -1_000_000))
        logger.debug(f'{api.units[uid].name} removed {looted_gold} gold from {api.units[loot_target]}')
        return looted_gold, loot_target, loot_pos

    @classmethod
    def apply_move(cls, api, uid, target=None, move_speed=None):
        if move_speed is None:
            move_speed = api.get_velocity(uid)
            logger.debug(f'apply_move using current move speed: {move_speed}')
        slow = api.get_status(uid, STATUS.SLOW)
        if slow > 0:
            move_speed *= max(0, cls.rp2reduction(slow))
        move_speed /= 100
        if target is None:
            target = api.get_position(uid, value_name=VALUE.TARGET)
        current_pos = api.get_position(uid)
        target_vector = target - current_pos
        delta = normalize(target_vector, move_speed)
        api.set_position(uid, delta, value_name=VALUE.DELTA)
        api.set_position(uid, target, value_name=VALUE.TARGET)

    @classmethod
    def apply_debuff(cls, api, targets, status, duration, stacks):
        if isinstance(targets, int) or isinstance(targets, np.int64):
            logger.debug(f'Applied status {status.name} {duration} × {stacks} to targets: {api.units[targets].name}')
        elif targets.sum() == 0:
            return
        else:
            logger.debug(f'Applied status {status.name} {duration} × {stacks} to {targets.sum()} targets')
        api.set_status(targets, status, duration, stacks)

    @classmethod
    def do_normal_damage(cls, api, source_uid, targets_mask, damage):
        # Stop if no targets
        if targets_mask.sum() == 0:
            return

        logger.debug(f'{source_uid} applying {damage:.2f} normal damage to {targets_mask.nonzero()[0]}')
        damages = targets_mask * damage
        damages = damages[targets_mask]
        # Armor reduction
        armor = cls.get_status(api, targets_mask, STAT.ARMOR)
        damages *= cls.rp2reduction(armor)

        # Converted pure damage
        cls.do_pure_damage(api, targets_mask, damages)

        # Spikes
        spike_damage = cls.get_status(api, targets_mask, STAT.SPIKES).sum()
        cls.do_pure_damage(api, cls.mask(api, source_uid), spike_damage)

        # Lifesteal
        lifesteal = cls.get_status(api, source_uid, STAT.LIFESTEAL) * sum(damages) / 100
        cls.do_heal(api, cls.mask(api, source_uid), lifesteal)

    @classmethod
    def do_blast_damage(cls, api, source_uid, targets_mask, damage):
        logger.debug(f'{source_uid} applying {damage:.2f} blast damage to {targets_mask.nonzero()[0]}')
        damages = targets_mask * damage
        damages = damages[targets_mask]

        # Vanity amplification
        vanity = cls.get_status(api, targets_mask, STAT.VANITY)
        damages *= 1 + (vanity / 100)

        # Converted pure damage
        cls.do_pure_damage(api, targets_mask, damages)

    @classmethod
    def do_pure_damage(cls, api, targets_mask, damages):
        if isinstance(damages, np.ndarray):
            damages[damages<0] = 0
        elif damages < 0:
            damages = 0
        api.set_stats(targets_mask, STAT.HP, -damages, additive=True)
        # Play ouch feedback if player uid is in targets
        if targets_mask[0] > 0:
            api.add_visual_effect(VisualEffect.BACKGROUND, 40)
            api.add_visual_effect(VisualEffect.SFX, 1, params={'sfx': 'ouch', 'category': 'ui', 'volume': 'feedback'})
        # Check if non player is in list
        if targets_mask.sum() - targets_mask[0] > 0:
            api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'hit', 'category': 'ui', 'volume': 'feedback'})
        logger.debug(f'{targets_mask.nonzero()[0]} took {damages} pure damage.')

    @classmethod
    def do_heal(cls, api, targets_mask, heal):
        if isinstance(heal, np.ndarray):
            heal[heal<0] = 0
        elif heal < 0:
            heal = 0
        api.set_stats(targets_mask, STAT.HP, heal, additive=True)
        logger.debug(f'{targets_mask.nonzero()[0]} healed by {heal}.')

    # Utilities
    @classmethod
    def mask(cls, api, targets):
        a = np.zeros(api.unit_count, dtype=np.bool)
        a[targets] = True
        return a

    @staticmethod
    def rp2reduction(rp):
        return ((rp + 50) ** -1) * 50

    @classmethod
    def get_status(cls, api, uid, stat):
        base = api.get_stats(uid, stat)
        from_status = api.get_status(uid, cls.STATUSES[stat])
        return base + from_status
