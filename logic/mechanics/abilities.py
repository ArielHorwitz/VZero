
import numpy as np
import math
from pathlib import Path
from nutil.file import file_load
from nutil.vars import normalize
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics as Mech



class Ability:
    def __init__(self, aid, name):
        self.name = name
        self.aid = aid

    def cast(self, aid, uid, target):
        raise NotImplementedError(f'Ability {self.aid} cast method not implemented')


class Teleport(Ability):
    def __init__(self, aid, name,
                 mana_cost=50, range=300,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.range = range

    def cast(self, api, uid, target):
        pos = api.get_position(uid)
        # Check
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if math.dist(pos, target) > self.range:
            fixed_vector = normalize(target - pos, self.range)
            target = pos + fixed_vector
        # Apply
        api.set_position(uid, target, value_name=(
            VALUE.CURRENT, VALUE.TARGET_VALUE))
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        api.add_visual_effect(VisualEffect.LINE, 15, params={
            'p1': pos,
            'p2': target,
            'color_code': -1,
        })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'blink'})
        return self.aid


class Slow(Ability):
    def __init__(self, aid, name,
                 mana_cost=50,
                 cooldown=600,
                 duration=240,
                 percent=50,
                 range=400,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.duration = duration
        self.percent = percent / 100
        self.range = range

    def cast(self, api, uid, target):
        # Check
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        target_uid = api.find_enemy_target(uid, target, range=self.range)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        # Apply
        print(f'{uid} applied beam on {target_uid}')
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        Mech.apply_slow(api, target_uid, self.duration, self.percent)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color_code': api.units[uid].color_code,
        })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'beam'})
        return self.aid


class Lifesteal(Ability):
    def __init__(self, aid, name,
                 mana_cost=25,
                 cooldown=7200,
                 duration=960,
                 percent=100,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.duration = duration
        self.percent = percent / 100

    def cast(self, api, uid, target):
        # Check
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        # Apply
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_status(uid, STATUS.LIFESTEAL, self.duration, self.percent)
        if uid == 0:
            api.add_visual_effect(VisualEffect.BACKGROUND, self.duration)
        return self.aid


class DefaultAbilities:
    @classmethod
    def move(cls, api, uid, target):
        Mech.apply_move(api, uid, target=target)
        return ABILITIES.MOVE

    @classmethod
    def loot(cls, api, uid, target):
        ability = ABILITIES.LOOT
        pos = api.get_position(uid)
        range = 150
        # Check
        golds = api.get_stats(index=slice(None), stat=STAT.GOLD)
        mask_gold = golds > 0
        lootables = np.logical_and(api.mask_dead(), mask_gold)
        loot_target, dist = api.nearest_uid(pos, mask=lootables, alive=False)
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

    @classmethod
    def stop(cls, api, uid, target):
        current_pos = api.get_position(uid)
        cls.move(api, uid, current_pos)
        return ABILITIES.STOP

    @classmethod
    def attack(cls, api, uid, target):
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

    @classmethod
    def vial(cls, api, uid, target):
        ability = ABILITIES.VIAL
        gold_cost = 50
        damage_buff = 10
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.DAMAGE, damage_buff, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability

    @classmethod
    def shard(cls, api, uid, target):
        ability = ABILITIES.SHARD
        gold_cost = 30
        attack_speed_buff = 10
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.ATTACK_SPEED, attack_speed_buff, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability

    @classmethod
    def moonstone(cls, api, uid, target):
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

    @classmethod
    def branch(cls, api, uid, target):
        ability = ABILITIES.BRANCH
        gold_cost = 10
        move_speed = 0.05
        if api.get_stats(uid, STAT.GOLD) < gold_cost:
            return FAIL_RESULT.MISSING_COST
        api.set_stats(uid, STAT.GOLD, -gold_cost, additive=True)
        api.set_stats(uid, STAT.MOVE_SPEED, move_speed, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'consume'})
        return ability


ABILITY_TYPES = {
    'teleport': Teleport,
    'slow': Slow,
    'lifesteal': Lifesteal,
}
