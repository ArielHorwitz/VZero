
import numpy as np
import math
from pathlib import Path
from nutil.file import file_load
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics as Mech


class Abilities:
    @staticmethod
    def move(api, uid, target):
        Mech.apply_move(api, uid, target=target)
        return ABILITIES.MOVE

    @staticmethod
    def loot(api, uid, target):
        ability = ABILITIES.LOOT
        pos = api.get_position(uid)
        range = api.get_stats(uid, STAT.RANGE)
        # Check
        golds = api.get_stats(index=slice(None), stat=STAT.GOLD)
        mask_gold = golds > 0
        lootables = np.logical_and(api.mask_dead(), mask_gold)
        loot_target, dist = api.nearest_uid(target, mask=lootables, alive=False)
        if loot_target is None:
            return FAIL_RESULT.MISSING_TARGET
        loot_pos = api.get_position(loot_target)
        if math.dist(pos, loot_pos) > range:
            return FAIL_RESULT.OUT_OF_RANGE
        # Apply
        looted_gold = api.get_stats(loot_target, STAT.GOLD)
        api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
        api.set_stats(loot_target, STAT.GOLD, 0)
        # Move remains
        api.set_stats(loot_target, (STAT.POS_X, STAT.POS_Y), (-5000, -5000))
        print(f'Looted: {looted_gold} from {api.units[loot_target].name}')
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'loot'})
        return ABILITIES.LOOT

    @staticmethod
    def blink(api, uid, target):
        ability = ABILITIES.BLINK
        mana_cost = 50
        blink_range_factor = 50
        pos = api.get_position(uid)
        range = api.get_stats(uid, STAT.RANGE, VALUE.CURRENT)
        # Check
        if api.get_stats(uid, STAT.MANA) < mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, ability) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if math.dist(pos, target) > range * blink_range_factor:
            return FAIL_RESULT.OUT_OF_RANGE
        # Apply
        for axis, stat in enumerate((STAT.POS_X, STAT.POS_Y)):
            for value in (VALUE.CURRENT, VALUE.TARGET_VALUE):
                api.set_stats(uid, stat, target[axis], value_name=value)
        api.set_stats(uid, STAT.MANA, -mana_cost, additive=True)
        api.add_visual_effect(VisualEffect.LINE, 15, params={
            'p1': pos,
            'p2': target,
            'color_code': -1,
        })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'blink'})
        return ability

    @staticmethod
    def stop(api, uid, target):
        current_pos = api.get_position(uid)
        Abilities.move(api, uid, current_pos)
        return ABILITIES.STOP

    @staticmethod
    def attack(api, uid, target):
        ability = ABILITIES.ATTACK
        attack_speed = api.get_stats(uid, STAT.ATTACK_SPEED, VALUE.CURRENT)
        cooldown = api.attack_speed_to_cooldown(attack_speed)
        # Check
        if api.get_cooldown(uid, ability) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        target_uid = api.find_enemy_target(uid, target)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        # Apply
        damage = api.get_stats(uid, STAT.DAMAGE, VALUE.CURRENT)
        api.set_cooldown(uid, ability, cooldown)
        Mech.do_physical_damage(api, uid, target_uid, damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color_code': api.units[uid].color_code,
        })
        if uid == 0:
            api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'attack'})
        return ABILITIES.ATTACK

    @staticmethod
    def bloodlust(api, uid, target):
        ability = ABILITIES.BLOODLUST
        mana_cost = 25
        cooldown = 120*60
        duration = 120*8
        lifesteal = 1
        # Check
        if api.get_stats(uid, STAT.MANA) < mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, ability) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        # Apply
        api.set_stats(uid, STAT.MANA, -mana_cost, additive=True)
        api.set_cooldown(uid, ability, cooldown)
        api.set_status(uid, STATUS.LIFESTEAL, duration, lifesteal)
        if uid == 0:
            api.add_visual_effect(VisualEffect.BACKGROUND, duration)
        return ability

    @staticmethod
    def beam(api, uid, target):
        ability = ABILITIES.BEAM
        cooldown = 600
        mana_cost = 50
        duration = 240
        percent = 0.5
        range = api.get_stats(uid, STAT.RANGE, VALUE.CURRENT) * 3
        # Check
        if api.get_stats(uid, STAT.MANA) < mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, ability) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        target_uid = api.find_enemy_target(uid, target, range=range)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        # Apply
        print(f'{uid} applied beam on {target_uid}')
        api.set_cooldown(uid, ability, cooldown)
        api.set_stats(uid, STAT.MANA, -mana_cost, additive=True)
        Mech.apply_slow(api, target_uid, duration, percent)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color_code': api.units[uid].color_code,
        })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'beam'})
        return ability

    @staticmethod
    def vial(api, uid, target):
        ability = ABILITIES.VIAL
        gold_cost = 50
        damage_buff = 10
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.DAMAGE, damage_buff, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability

    @staticmethod
    def shard(api, uid, target):
        ability = ABILITIES.SHARD
        gold_cost = 30
        attack_speed_buff = 10
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.ATTACK_SPEED, attack_speed_buff, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability

    @staticmethod
    def moonstone(api, uid, target):
        ability = ABILITIES.MOONSTONE
        gold_cost = 25
        max_hp_buff = 5
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.HP, max_hp_buff, value_name=VALUE.MAX_VALUE, additive=True)
        api.set_stats(uid, STAT.HP, max_hp_buff, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability

    @staticmethod
    def branch(api, uid, target):
        ability = ABILITIES.BRANCH
        gold_cost = 10
        move_speed = 0.05
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.MOVE_SPEED, move_speed, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability
