
import numpy as np
from logic.mechanics.common import *
from nutil.vars import normalize
from nutil.random import SEED

import logging
logger = logging.getLogger(__name__)

import numpy as np
import math

class Mechanics:
    @staticmethod
    def attack_speed_to_cooldown(api, uid, attack_speed):
        wrath_stacks = api.get_status(uid,STATUS.WRATH)
        return (100 / (attack_speed + wrath_stacks * 20)) * 120

    def find_enemy_target(api, uid, target,
            range=None, include_hitbox=True,
            draw_miss_vfx=True, mask=None,
        ):
        pos = api.get_position(uid)
        if range is None:
            range = float('inf')
        enemies = api.mask_enemies(uid)
        if mask is not None:
            enemies = np.logical_and(enemies, mask)
        target_uid, dist = api.nearest_uid(target, enemies)
        if target_uid is None:
            return None
        attack_pos = api.get_position(target_uid)
        attack_target = api.units[target_uid]
        if include_hitbox:
            range += api.get_stats(target_uid, STAT.HITBOX)
        if math.dist(pos, attack_pos) > range:
            if draw_miss_vfx and uid == 0:
                self.add_visual_effect(VisualEffect.LINE, 10, {
                    'p1': pos,
                    'p2': pos + normalize(attack_pos - pos, range),
                    'color': api.units[uid].color,
                })
            return None
        return target_uid

    @staticmethod
    def apply_move(api, uid, target=None, move_speed=None):
        if move_speed is None:
            move_speed = api.get_stats(uid, STAT.MOVE_SPEED)
            if api.get_status(uid, STATUS.SLOW) > 0:
                move_speed *= 1-api.get_status(uid, STATUS.SLOW)
        if target is None:
            target = api.get_position(uid, value_name=VALUE.TARGET_VALUE)
        current_pos = api.get_position(uid)
        target_vector = target - current_pos
        delta = normalize(target_vector, move_speed)
        api.set_position(uid, delta, value_name=VALUE.DELTA)
        api.set_position(uid, target, value_name=VALUE.TARGET_VALUE)

    @staticmethod
    def apply_slow(api, uid, duration, percent):
        api.set_status(uid, STATUS.SLOW, duration, percent)
        Mechanics.apply_move(api, uid)

    @staticmethod
    def do_physical_damage(api, source_uid, target_uid, damage):
        source = api.units[source_uid]
        target = api.units[target_uid]
        block_percent = 0
        block_chance = api.get_status(target_uid,STATUS.SHIELD_CHANCE)
        if block_chance >= SEED.r:
            block_percent = api.get_status(target_uid,STATUS.SHIELD_BLOCK)
        damage -= block_percent * damage
        wrath_stacks = api.get_status(source_uid, STATUS.WRATH)
        damage += (wrath_stacks/3) * damage
        api.set_stats(target_uid, STAT.HP, -damage, additive=True)
        lifesteal = api.get_stats(source_uid, STAT.LIFESTEAL)
        lifesteal += api.get_status(source_uid, STATUS.LIFESTEAL)
        api.set_stats(source_uid, STAT.HP, damage*lifesteal, additive=True)
        if target_uid == 0:
            api.add_visual_effect(VisualEffect.BACKGROUND, 40)
            api.add_visual_effect(VisualEffect.SFX, 1, params={'sfx': 'ouch', 'category': 'ui'})
        if target_uid == 0 or source_uid == 0:
            logger.debug(f'{source.name} applied {damage:.2f} damage to {target.name}')

    @staticmethod
    def get_aoe_targets(api, point, radius, mask=None):
        in_radius = api.get_distances(point) < radius
        if mask is not None:
            in_radius = np.logical_and(in_radius, mask)
        return in_radius
