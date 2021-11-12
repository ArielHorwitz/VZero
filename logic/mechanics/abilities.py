
import numpy as np
import math
from pathlib import Path
from nutil.file import file_load
from nutil.vars import normalize
from nutil.display import njoin
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics as Mech

import logging
logger = logging.getLogger(__name__)


class Ability:
    def __init__(self, aid, name):
        self.name = name
        self.aid = aid
        self.color = (0.25, 0.25, 0.25)

    @property
    def sprite(self):
        return self.aid.name.lower()

    def cast(self, aid, uid, target):
        raise NotImplementedError(f'Ability {self.aid} cast method not implemented')

    @property
    def description(self):
        return f'No description available (#{self.aid})'


class Move(Ability):
    def __init__(self, aid, name,
                 mana_cost=0,
                 range=1_000_000,
                 cooldown=0,
                 speed_multiplier=1,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.range = range
        self.cooldown = cooldown
        self.speed_multiplier = speed_multiplier

    def cast(self, api, uid, target):
        # Check
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        pos = api.get_position(uid)
        if math.dist(pos, target) > self.range:
            return FAIL_RESULT.OUT_OF_RANGE
        move_speed = api.get_stats(uid, STAT.MOVE_SPEED) / 100 * self.speed_multiplier
        Mech.apply_move(api, uid, target=target, move_speed=move_speed)
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Move to target.',
            '',
            f'Speed multiplier: {self.speed_multiplier}',
            f'Mana cost: {self.mana_cost}',
            f'Range: {self.range}',
            f'Cooldown: {self.cooldown}',
        ])


class Loot(Ability):
    def __init__(self, aid, name,
                 mana_cost=0,
                 range=150,
                 cooldown=0,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.range = range
        self.cooldown = cooldown

    def cast(self, api, uid, target):
        pos = api.get_position(uid)
        # Check
        golds = api.get_stats(index=slice(None), stat=STAT.GOLD)
        mask_gold = golds > 0
        lootables = np.logical_and(api.mask_dead(), mask_gold)
        loot_target, dist = api.nearest_uid(pos, mask=lootables, alive=False)
        if loot_target is None:
            return FAIL_RESULT.MISSING_TARGET
        loot_pos = api.get_position(loot_target)
        if math.dist(pos, loot_pos) > self.range:
            return FAIL_RESULT.OUT_OF_RANGE
        # Apply
        looted_gold = api.get_stats(loot_target, STAT.GOLD)
        api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
        api.set_stats(loot_target, STAT.GOLD, 0)
        # Move remains
        api.set_stats(loot_target, (STAT.POS_X, STAT.POS_Y), (-1_000_000, -1_000_000))
        logger.debug(f'Looted: {looted_gold} from {api.units[loot_target].name}')
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'coin'})
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Loot the dead. Take any remaining gold.',
            '',
            f'Range: {self.range}',
            f'Mana cost: {self.mana_cost}',
            f'Cooldown: {self.cooldown}',
        ])


class Attack(Ability):
    def __init__(self, aid, name,
                 mana_cost=0,
                 range=100,
                 cooldown=150,
                 damage_multiplier=1
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.range = range
        self.cooldown = cooldown
        self.damage_multiplier = damage_multiplier
        self.color = (0.6, 0.8, 0)

    def cast(self, api, uid, target):
        # Check
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        target_uid = api.find_enemy_target(uid, target)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        damage = api.get_stats(uid, STAT.DAMAGE, VALUE.CURRENT) * self.damage_multiplier
        # Apply
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        api.set_cooldown(uid, self.aid, self.cooldown)
        Mech.do_physical_damage(api, uid, target_uid, damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            # 'color_code': api.units[uid].color_code,
        })
        if uid == 0:
            api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'attack'})
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Deal physical damage to a single target.',
            '',
            f'Range: {self.range}',
            f'Mana cost: {self.mana_cost}',
            f'Cooldown: {self.cooldown}',
            f'Damage: {self.damage_multiplier} x <Damage>',
        ])


class Teleport(Ability):
    def __init__(self, aid, name,
                 mana_cost=50,
                 range=300,
                 cooldown=200,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.range = range
        self.cooldown = cooldown
        self.color = (0.6, 0.8, 0)

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
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_position(uid, target, value_name=(
            VALUE.CURRENT, VALUE.TARGET_VALUE))
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'blink'})
        api.add_visual_effect(VisualEffect.SPRITE, 50, {
            'stretch': (pos, target),
            'fade': 20,
            # 'point': api.get_position(uid),
            'source': 'beam',
        })
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Instantly teleport to target.',
            '',
            f'Mana cost: {self.mana_cost}',
            f'Range: {self.range}',
            f'Cooldown: {self.cooldown}',
        ])


class Slow(Ability):
    def __init__(self, aid, name,
                 mana_cost=50,
                 cooldown=600,
                 duration=240,
                 percent=50,
                 range=400,
                 damage_percent=0,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.duration = duration
        self.percent = percent / 100
        self.range = range
        self.damage = damage_percent / 100
        self.color = (0.4, 0.4, 0)

    def cast(self, api, uid, target):
        # Check
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        target_uid = api.find_enemy_target(uid, target, range=self.range)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        damage = api.get_stats(target_uid, STAT.HP) * self.damage
        # Apply
        logger.debug(f'{api.units[uid].name} used {self.name} on {api.units[target_uid].name}')
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        Mech.do_physical_damage(api, uid, target_uid, damage)
        Mech.apply_slow(api, target_uid, self.duration, self.percent)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            # 'color_code': api.units[uid].color_code,
        })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'slow'})
        return self.aid

    @property
    def description(self):
        dmg_str = f'\nDeal physical damage based on target\'s current HP.' if self.damage > 0 else ''
        percent_str = f'\nDamage: {self.damage*100}% of current HP' if self.damage > 0 else ''
        return njoin([
            f'Apply slow to a single target.{dmg_str}',
            '',
            f'Mana cost: {self.mana_cost}',
            f'Cooldown: {self.cooldown}',
            f'Range: {self.range}',
            f'Duration: {self.duration}',
            f'Slow: {self.percent*100}%{percent_str}',
        ])


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
        self.color = (1, 0, 0)

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
            api.add_visual_effect(VisualEffect.BACKGROUND, self.duration, params={'color': (1, 0, 0, 0.15)})
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Get temporary lifesteal.',
            '',
            f'Mana cost: {self.mana_cost}',
            f'Cooldown: {self.cooldown}',
            f'Lifesteal %: {self.percent*100:.1f}',
            f'Duration: {self.duration}',
        ])


class Shield(Ability):
    def __init__(self, aid, name,
                 hp_cost_percent= 5,
                 cooldown=2400,
                 duration=800,
                 chance_percent=69,
                 block_percent=69,
                 ):
        super().__init__(aid, name)
        self.hp_cost = hp_cost_percent / 100
        self.cooldown = cooldown
        self.duration = duration
        self.chance = chance_percent / 100
        self.block = block_percent / 100
        self.color = (0, 0, 1)


    def cast(self, api, uid, target):
        hitbox = api.get_stats(uid, STAT.HITBOX)
        # Check
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        # Apply
        api.set_stats(uid, STAT.HP, 1-self.hp_cost, multiplicative=True)
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_status(uid, STATUS.SHIELD_CHANCE, self.duration, self.chance)
        api.set_status(uid, STATUS.SHIELD_BLOCK, self.duration, self.block)

        api.add_visual_effect(
            VisualEffect.CIRCLE, self.duration, params={
                'color': (0, 0.3, 1, 0.3),
                'radius': hitbox*3,
                'uid': uid,
            })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'shield'})
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Gain a temporary shield. Has a chance to block damage.',
            '',
            f'HP cost: {self.hp_cost*100:.1f}',
            f'Cooldown: {self.cooldown:.1f}',
            f'Block chance: {self.chance*100:.1f}',
            f'Damage block %: {self.block*100:.1f}',
            f'Duration: {self.duration:.1f}',
        ])


class Blast(Ability):
    def __init__(self, aid, name,
                 mana_cost=30,
                 cooldown=5000,
                 range=500,
                 radius=300,
                 damage=0,
                 ):
        super().__init__(aid, name)
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.range = range
        self.radius = radius
        self.damage = damage
        self.color = (0.3, 1, 0.2)

    def cast(self, api, uid, target):
        if self.damage == 0:
            damage = api.get_stats(uid, STAT.DAMAGE) / 2
        else:
            damage = self.damage
        # Check
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN

        pos = api.get_position(uid)
        if math.dist(pos, target) > self.range:
            target = normalize(target - pos, self.range) + pos

        # Apply
        logger.debug(f'{api.units[uid].name} used {self.name} at {target}')
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        targets_mask = Mech.get_aoe_targets(api, target, self.radius, api.mask_enemies(uid))
        api.set_stats(targets_mask, STAT.HP, -damage, additive=True)

        api.add_visual_effect(VisualEffect.CIRCLE, 30, {
            'center': target,
            'radius': self.radius,
            'color': (*COLOR.RED, 0.5),
            'fade': 30,
        })
        api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'explosion'})
        return self.aid

    @property
    def description(self):
        return njoin([
            f'Deal damage in an area.',
            '',
            f'Mana cost: {self.mana_cost:.1f}',
            f'Cooldown: {self.cooldown:.1f}',
            f'Range: {self.range:.1f}',
            f'Radius: {self.radius:.1f}',
        ])


class Mindcontrol(Ability):
    def __init__(self,aid,name,
                 mana_cost_percent = 80,
                 range = 100,
                 hp_margin_percent = 33,
                 ):
        super().__init__(aid,name)
        self.mana_cost = mana_cost_percent / 100
        self.range = range
        self.hp_margin = hp_margin_percent / 100
        self.color = (0.3, 0, 0.7)

    def cast(self, api, uid, target):
        max_mana = api.get_stats(uid, STAT.MANA, value_name=VALUE.MAX_VALUE)
        if api.get_stats(uid, STAT.MANA) <= (max_mana * self.mana_cost):
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        max_hps = api.get_stats(slice(None),STAT.HP,value_name=VALUE.MAX_VALUE)
        current_hps = api.get_stats(slice(None),STAT.HP)

        precent_mask = current_hps < (max_hps * self.hp_margin)
        target_uid = api.find_enemy_target(uid, target, range=self.range, mask=precent_mask)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET

        enemy_max_hp = api.get_stats(target_uid,STAT.HP, value_name=VALUE.MAX_VALUE)
        if api.get_stats(target_uid,STAT.HP) <= (enemy_max_hp * self.hp_margin):
            api.units[target_uid].allegience = api.units[uid].allegience

        return self.aid


class Wrath(Ability):
    def __init__(self,aid,name,
                 hp_cost_percent = 50,
                 duration = 1200,
                 ):
        super().__init__(aid, name)
        self.hp_cost = hp_cost_percent / 100
        self.duration = duration
        self.color = (1, 0.4, 0)

    def cast(self, api, uid, target):

        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        api.set_stats(uid, STAT.HP, 1 - self.hp_cost, multiplicative=True)
        stacks = api.get_status(uid,STATUS.WRATH, value_name=STATUS_VALUE.AMPLITUDE) + 1
        api.set_status(uid, STATUS.WRATH, self.duration, stacks)

        return self.aid


class DefaultAbilities:
    class Move(Ability):
        def cast(self, api, uid, target):
            Mech.apply_move(api, uid, target=target)
            return ABILITIES.MOVE

    class Loot(Ability):
        def cast(self, api, uid, target):
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
            logger.debug(f'Looted: {looted_gold} from {api.units[loot_target].name}')
            api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': 'coin'})
            return self.aid

    @classmethod
    def stop(cls, api, uid, target):
        current_pos = api.get_position(uid)
        cls.move(api, uid, current_pos)
        return ABILITIES.STOP

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
    'shield': Shield,
    'blast': Blast,
    'mindcontrol': Mindcontrol,
    'wrath': Wrath,
    'attack': Attack,
    'loot': Loot,
    'move': Move,
}
