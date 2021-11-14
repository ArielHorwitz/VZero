import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


import itertools
import numpy as np
import math
from nutil.vars import normalize
from nutil.display import njoin
from logic.mechanics.common import *
from logic.mechanics.ability import Ability as BaseAbility
from logic.mechanics import import_mod_module
Mechanics = import_mod_module('mechanics').Mechanics


class Params:
    @classmethod
    def get_elemental_stat(cls, api, uid, string, cap_minimum=0.1):
        v = 0
        if string is not None:
            v = api.get_stats(uid, str2stat(string))
        v = max(cap_minimum, v)
        return v

    @classmethod
    def get_stat_bonus_str(cls,
                           stat, coefficient,
                           prefix=' + ',
                           percent=True,
                           coefficient_suffix='',
                           divider=' × ',
                           stat_suffix=''):
        if percent:
            coefficient_suffix = '%'
            coefficient *= 100
        if stat is not None:
            return f'{prefix}{coefficient:.1f}{coefficient_suffix}{divider}{str2stat(stat).name.lower()}{stat_suffix}'
        else:
            return ''


class Ability(BaseAbility):
    def setup(self, **params):
        self._params = None
        for k, v in params.items():
            if k not in tuple(self.defaults.keys()):
                logger.warning(f'Setting up parameter {k} for ability {self.name} but no existing default')
        if self.defaults is None:
            logger.error(f'{self.__class__} missing defaults')
            self.defaults = {}
        self._params = {**self.defaults, **params}
        logger.debug(f'Created ability {self.name} with arguments: {params}. Defaults: {self.defaults}')

    def __getattr__(self, x):
        if self._params is not None and x != '_params':
            if x in self._params:
                return self.get_param(x)
            else:
                raise AttributeError(f'{self.__class__} has no attribute {x}')

    def get_param(self, param):
        return self._params[param]

    def get_elemental_bonus(self, api, uid, bonus_name,
                            stat_value_mod=None,
                            percent=False,
                            cap_minimum=0.1,
                            ):
        stat_name = self.get_param(f'{bonus_name}_stat')
        elemental_stat_value = api.get_stats(uid, str2stat(stat_name))
        if stat_value_mod is not None:
            elemental_stat_value = stat_value_mod(elemental_stat_value)
        if percent:
            elemental_stat_value /= 100
        multiplier = self.get_param(f'{bonus_name}_bonus')
        bonus = elemental_stat_value * multiplier
        logger.debug(f'Ability {self.name} calculated bonus: {bonus} ({elemental_stat_value} * {multiplier})')
        return bonus


class Move(Ability):
    defaults = {
        'mana_cost': 0,
        'range': 1_000_000,
        'cooldown': 0,
        'base_speed': 20,
        'speed_stat': 'water',
        'speed_multiplier': 10,
    }

    def cast(self, api, uid, target):
        # check cooldown, mana, range
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if math.dist(api.get_position(uid), target) > self.range:
            return FAIL_RESULT.OUT_OF_RANGE

        # Apply
        speed_bonus = self.speed_multiplier * math.sqrt(
            Params.get_elemental_stat(api, uid, self.speed_stat, cap_minimum=1))
        move_speed = self.base_speed + speed_bonus
        if self.cooldown:
            api.set_cooldown(uid, self.aid, self.cooldown)
        Mechanics.apply_move(api, uid, target=target, move_speed=move_speed)
        return self.aid

    @property
    def description(self):
        speed_str = Params.get_stat_bonus_str(self.speed_stat, self.speed_multiplier, divider=' × √', percent=False)
        return njoin([
            f'Move to a target position.',
            f'Class: {self.__class__.__name__}',
            '',
            f'Mana cost: {self.mana_cost}',
            f'Range: {self.range}',
            f'Cooldown: {self.cooldown}',
            f'Speed: {self.base_speed}{speed_str}',
        ])


class Barter(Ability):
    def setup(self,
              mana_cost=0,
              range=150,
              cooldown=10000,
              bonus_percent=10,
              bonus_stat='physical',
              ):
        self.mana_cost = mana_cost
        self.range = range
        self.cooldown = cooldown
        self.bonus_stat = str2stat(bonus_stat)
        self.bonus = bonus_percent / 100

    def cast(self, api, uid, target):
        # loot nearest target regardless of check
        looted_gold, loot_pos = Mechanics.apply_loot(api, uid, api.get_position(uid), self.range)
        # return fail result if no loot
        if isinstance(looted_gold, FAIL_RESULT):
            logger.debug(f'Barter failed with {looted_gold}')
            return looted_gold

        # check cooldown, mana for bonus gold
        if all([
            api.get_cooldown(uid, self.aid) <= 0,
            api.get_stats(uid, STAT.MANA) > self.mana_cost,
            ]):
            looted_gold += looted_gold * self.bonus * api.get_stats(uid, self.bonus_stat)
            # cooldown, mana cost
            api.set_cooldown(uid, self.aid, self.cooldown)
            api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)

        # gold income effect
        api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
        api.add_visual_effect(VisualEffect.SPRITE, 50, params={
            'source': 'coin',
            'point': loot_pos,
            'fade': 50,
            'size': (25, 25),
            })
        return self.aid


    @property
    def description(self):
        return njoin([
            f'"Hello there, corpse. I see your negotiation capabilities have diminished drastically."',
            '',
            f'Class: {self.__class__.__name__}',
            f'Mana cost: {self.mana_cost}',
            f'Range: {self.range}',
            f'Cooldown: {self.cooldown}',
            f'Bonus gold: {self.bonus*100:.1f}% × {self.bonus_stat.name.lower()}',
        ])


class Attack(Ability):
    def setup(self,
              mana_cost=0,
              range=100,
              cooldown=150,
              base_damage=20,
              damage_stat='physical',
              damage_percent=2,
              ):
        self.mana_cost = mana_cost
        self.range = range
        self.cooldown = cooldown
        self.base_damage = base_damage
        self.damage_stat = damage_stat
        self.damage_percent = damage_percent / 100
        self.color = (0.6, 0.8, 0)

    def cast(self, api, uid, target):

        # check mana, cooldown, range (find target)
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        target_uid = Mechanics.find_target(api, uid, target, range=self.range)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET

        # get damage percent multiplier from elemental stats
        damage_bonus = self.damage_percent * Params.get_elemental_stat(api, uid, self.damage_stat)
        damage = self.base_damage * (1+damage_bonus)

        # cooldown, mana cost
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        api.set_cooldown(uid, self.aid, self.cooldown)

        # damage effect
        Mechanics.do_brute_damage(api, uid, target_uid, damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color': api.units[uid].color,
        })
        return self.aid

    @property
    def description(self):
        damage_str = Params.get_stat_bonus_str(self.damage_stat, self.damage_percent)
        return njoin([
            f'Deal brute damage to a single target.',
            '',
            f'Class: {self.__class__.__name__}',
            f'Mana cost: {self.mana_cost}',
            f'Range: {self.range}',
            f'Cooldown: {self.cooldown}',
            f'Damage: {self.base_damage}{damage_str}',
        ])


class Buff(Ability):
    def setup(self,
              mana_cost=50,
              cooldown=600,
              range=150,
              target='self',  # 'self' or 'other'
              status=None,
              # stacks
              stacks=1,
              stacks_stat=None,
              stacks_percent=1,
              # duration
              duration=240,
              duration_stat=None,
              duration_percent=1,
              ):
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.range = range
        self.target = target
        self.status = str2status(status)
        self.duration = duration
        self.stacks = stacks
        self.stacks_stat = stacks_stat
        self.stacks_percent = stacks_percent / 100
        self.duration_stat = duration_stat
        self.duration_percent = duration_percent / 100
        self.color = (0.4, 0.4, 0)

    def cast(self, api, uid, target):

        # check mana, cooldown, range (find target)
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        if self.target == 'self':
            target_uid = uid
        else:
            target_uid = Mechanics.find_target_enemy(api, uid, target, range=self.range)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET
        logger.debug(f'{api.units[uid].name} using {self.name} on {api.units[target_uid].name}')

        # get duration+stacks percent multiplier from elemental stats
        stacks_bonus = Params.get_elemental_stat(api, uid, self.stacks_stat) * self.stacks_percent
        duration_bonus = Params.get_elemental_stat(api, uid, self.duration_stat) * self.duration_percent
        duration = self.duration * (1 + duration_bonus)
        stacks = self.stacks * (1 + stacks_bonus)

        # cooldown and mana cost
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)

        # status effect
        Mechanics.apply_debuff(api, target_uid, self.status, duration, stacks)
        if self.target == 'self':
            vfx_target = uid
        if self.target == 'other':
            vfx_target = target_uid
            api.add_visual_effect(VisualEffect.LINE, 5, {
                'p1': api.get_position(uid),
                'p2': api.get_position(target_uid),
                'color': api.units[uid].color,
            })
        api.add_visual_effect(VisualEffect.CIRCLE, duration, params={
            'color': (*self.color, 0.7),
            'radius': api.get_stats(vfx_target, STAT.HITBOX)*2,
            'uid': vfx_target,
            'fade': duration*4,
        })
        return self.aid

    @property
    def description(self):
        duration_str = Params.get_stat_bonus_str(self.duration_stat, self.duration_percent)
        stacks_str = Params.get_stat_bonus_str(self.stacks_stat, self.stacks_percent)
        return njoin([
            f'Apply {self.status.name.lower()} to a single target ({self.target}).',
            f'Class: {self.__class__.__name__}'
            '',
            f'Mana cost: {self.mana_cost}',
            f'Cooldown: {self.cooldown}',
            f'Range: {self.range}',
            f'Status: {self.status}',
            f'Duration: {self.duration}{duration_str}',
            f'Stacks: {self.stacks}{stacks_str}',
        ])


class Consume(Ability):
    def setup(self, *a, **k):
        super().setup(*a, **k)
        self.stat = itertools.cycle((STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER))
        self.next_stat = next(self.stat)

    def cast(self, api, uid, target):
        logger.debug(f'Casting {self.name}')
        v = api.get_stats(uid, self.next_stat)
        if (round(v) % 2) == 0:
            newv = v**2
            newv += 1
            self.next_stat = next(self.stat)
        else:
            newv = v-1
            newv = newv**(1/2)
        api.set_stats(uid, self.next_stat, newv)
        return self.aid


class Teleport(Ability):
    def setup(self,
              mana_cost=30,
              range=200,
              range_stat='air',
              range_percent=1,
              cooldown=600,
              cooldown_stat='water',
              cooldown_percent=0.5,
              ):
        self.mana_cost = mana_cost
        self.range = range
        self.range_stat = range_stat
        self.range_percent = range_percent / 100
        self.cooldown = cooldown
        self.cooldown_stat = cooldown_stat
        self.cooldown_percent = cooldown_percent / 100
        self.color = (0, 0, 0)

    def cast(self, api, uid, target):
        # get range percent multiplier from elemental stats
        range_bonus = Params.get_elemental_stat(api, uid, self.range_stat) * self.range_percent
        range = self.range * (1 + range_bonus)

        # check mana, cooldown, range (fix vector)
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        pos = api.get_position(uid)
        if math.dist(pos, target) > self.range:
            fixed_vector = normalize(target - pos, self.range)
            target = pos + fixed_vector
        logger.debug(f'{api.units[uid].name} teleporting to {target}')

        # get cooldown reduction from elemental stats
        cooldown_reduction = Params.get_elemental_stat(api, uid, self.cooldown_stat) * self.cooldown_percent
        cooldown = self.cooldown * (1 - min(0.99, cooldown_reduction))

        # cooldown and mana cost
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)

        # teleport effect
        api.set_position(uid, target)
        api.set_position(uid, target, value_name=VALUE.TARGET_VALUE)
        api.add_visual_effect(VisualEffect.SPRITE, 20, {
            'stretch': (pos, target),
            'fade': 20,
            'source': 'blink',
        })
        return self.aid

    @property
    def description(self):
        cd_str = Params.get_stat_bonus_str(self.cooldown_stat, self.cooldown_percent)
        range_str = Params.get_stat_bonus_str(self.range_stat, self.range_percent)
        return njoin([
            f'Instantly teleport to a target position.',
            f'Class: {self.__class__.__name__}'
            '',
            f'Mana cost: {self.mana_cost}',
            f'Cooldown: {self.cooldown}{cd_str}',
            f'Range: {self.range}{range_str}',
        ])


class Blast(Ability):
    defaults = {
        'mana_cost': 35,
        'cooldown': 500,
        'range': 300,
        'radius': 70,
        'damage': 20,
        'color': (0.3, 1, 0.2),
    }

    def cast(self, api, uid, target):
        # damage = min(0.1, api.get_stats(uid, STAT.FIRE))
        damage = self.damage
        # Check
        if api.get_stats(uid, STAT.MANA) < self.mana_cost:
            return FAIL_RESULT.MISSING_COST
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN

        pos = api.get_position(uid)
        if math.dist(pos, target) > self.range:
            return FAIL_RESULT.OUT_OF_RANGE

        # Apply
        logger.debug(f'{api.units[uid].name} used {self.name} at {target}')
        api.set_cooldown(uid, self.aid, self.cooldown)
        api.set_stats(uid, STAT.MANA, -self.mana_cost, additive=True)
        targets_mask = Mechanics.get_aoe_targets(api, target, self.radius, api.mask_enemies(uid))
        Mechanics.do_brute_damage(api, uid, targets_mask, damage)
        # api.set_stats(targets_mask, STAT.HP, -damage, additive=True)

        api.add_visual_effect(VisualEffect.CIRCLE, 30, {
            'center': target,
            'radius': self.radius,
            'color': (*COLOR.RED, 0.5),
            'fade': 30,
        })
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
