import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import itertools
import numpy as np
import math
from nutil.display import njoin
from logic.mechanics.common import *
from logic.mechanics import import_mod_module
BaseAbility = import_mod_module('abilities.ability').Ability
mechanics_mod = import_mod_module('mechanics')
Mechanics, Mutil = mechanics_mod.Mechanics, mechanics_mod.Utilities


class Move(BaseAbility):
    info = 'Move to a target position.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
        'range': 1_000_000,
        'speed': 20,
        'speed_stat': 'air',
        'speed_bonus': 10,
    }

    def do_cast(self, api, uid, target):
        speed = self.param_value(api, uid, 'speed')
        Mechanics.apply_move(api, uid, target=target, move_speed=speed)
        return self.aid


class Attack(BaseAbility):
    info = 'Deal brute damage to a single target.'
    lore = 'A time tested strategy. Use force.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 150,
        'range': 100,
        'damage': 20,
        'damage_stat': 'physical',
        'damage_add': 0.3,
    }

    def do_cast(self, api, uid, target):
        # check range (find target)
        range = self.param_value(api, uid, 'range')
        target_uid = f = Mutil.find_target_enemy(api, uid, target, range)
        if isinstance(f, FAIL_RESULT):
            return f

        # get damage percent multiplier from elemental stats
        damage = self.param_value(api, uid, 'damage')

        # damage effect
        Mechanics.do_brute_damage(api, uid, target_uid, damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color': api.units[uid].color,
        })
        return self.aid


class Barter(BaseAbility):
    info = 'Loot the dead, buy from shopkeepers.'
    lore = '"Hello there, corpse. I see your negotiation capabilities have diminished drastically."'
    defaults = {
        'mana_cost': 0,
        'range': 150,
        'cooldown': 10000,
        'loot': 1,
        'loot_stat': 'physical',
        'loot_bonus': 10,
        'loot_add': 2.5,
    }
    debug = True

    def cast(self, api, uid, target):
        # loot nearest target regardless of check
        range = self.param_value(api, uid, 'range')
        f, _ = looted_gold, loot_target = Mechanics.apply_loot(api, uid, api.get_position(uid), range)
        if isinstance(f, FAIL_RESULT):
            return f

        # check cooldown and mana for bonus gold
        if self.check_many(api, uid, checks=self.auto_check):
            self.cost_many(api, uid, costs=self.auto_cost)
            looted_gold *= self.param_value(api, uid, 'loot')

        # gold income effect
        api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
        api.add_visual_effect(VisualEffect.SPRITE, 50, params={
            'source': 'coin',
            'point': api.get_position(loot_target),
            'fade': 50,
            'size': (25, 25),
            })
        return self.aid


class Buff(BaseAbility):
    lore = 'Einstein called this one "spooky action at a distance".'
    color = (*COLOR.BLUE, 1)
    defaults = {
        'status': None,
        'target': 'self',  # 'self' or 'other'
        'mana_cost': 50,
        'cooldown': 600,
        'range': 150,
        'stacks': 1,
        'stacks_stat': None,
        'stacks_bonus': 1,
        'duration': 240,
        'duration_stat': None,
        'duration_bonus': 1,
        'color': (0, 0.1, 1)
        }
    debug = True

    def do_cast(self, api, uid, target):
        # find target
        if self.p.target == 'self':
            vfx_target = target_uid = uid
        else:
            range = self.param_value('range')
            vfx_target = target_uid = f = Mutil.find_target_enemy(api, uid, target, range)
            if isinstance(f, FAIL_RESULT):
                return f

        # status effect
        status = str2status(self.p.status)
        duration = self.param_value(api, uid, 'duration')
        stacks = self.param_value(api, uid, 'stacks')
        Mechanics.apply_debuff(api, target_uid, status, duration, stacks)

        # vfx
        if self.p.target == 'other':
            api.add_visual_effect(VisualEffect.LINE, 5, {
                'p1': api.get_position(uid),
                'p2': api.get_position(target_uid),
                'color': api.units[uid].color,
            })
        api.add_visual_effect(VisualEffect.CIRCLE, duration, params={
            'color': (*self.p.color, 0.7),
            'radius': api.get_stats(vfx_target, STAT.HITBOX)*2,
            'uid': vfx_target,
            'fade': duration*4,
        })
        return self.aid

    @property
    def info(self):
        return f'Apply {self.p.status} to a single target ({self.p.target}).'


class Consume(BaseAbility):
    debug = True
    def setup(self, *a, **k):
        super().setup(*a, **k)
        self.stat = itertools.cycle((STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER))
        self.next_stat = next(self.stat)

    def cast(self, api, uid, target):
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


class Teleport(BaseAbility):
    info = 'Instantly teleport to a target position.'
    lore = 'The ancient art of blinking goes back eons.'
    color = (*COLOR.GREEN, 1)
    defaults = {
        'mana_cost': 30,
        'cooldown': 600,
        'range': 200,
        'range_stat': 'air',
        'range_bonus': 1,
    }
    debug = True

    def do_cast(self, api, uid, target):
        range = self.param_value(api, uid, 'range')
        target = self.fix_vector(api, uid, target, range)
        # teleport effect
        api.set_position(uid, target)
        api.set_position(uid, target, VALUE.TARGET_VALUE)

        api.add_visual_effect(VisualEffect.SPRITE, 20, {
            'stretch': (api.get_position(uid), target),
            'fade': 20,
            'source': 'blink',
        })
        return self.aid


class Blast(BaseAbility):
    info = 'Deal brute damage in an area.'
    lore = 'Level 3 wizard! Let\'s GOOOO'
    color = (*COLOR.RED, 1)
    defaults = {
        'mana_cost': 35,
        'cooldown': 500,
        'range': 300,
        'radius': 30,
        'radius_stat': 'water',
        'radius_add': 0.1,
        'damage': 10,
        'damage_stat': 'fire',
        'damage_bonus': 2,
    }
    auto_check = {'mana', 'cooldown', 'range_point'}
    debug = True

    def do_cast(self, api, uid, target):
        damage = self.param_value(api, uid, 'damage')
        radius = self.param_value(api, uid, 'radius')
        targets_mask = Mutil.find_aoe_targets(api, target, radius, api.mask_enemies(uid))
        Mechanics.do_brute_damage(api, uid, targets_mask, damage)

        api.add_visual_effect(VisualEffect.CIRCLE, 30, {
            'center': target,
            'radius': radius,
            'color': (*COLOR.RED, 0.5),
            'fade': 30,
        })
        return self.aid


class RegenAura(BaseAbility):
    lore = 'Bright and dark mages are known for their healing and life draining abilities.'
    defaults = {
        'restat': None,
        'regen': 0.01,
        'destat': 'hp',
        'degen': 0.01,
        'radius': 350,
        'radius_stat': 'water',
        'radius_bonus': 1,
    }
    auto_check = set()
    auto_cost = set()

    def cast(self, api, uid, target):
        return self.aid

    def passive(self, api, uid, dt):
        radius = self.param_value(api, uid, 'radius')
        targets = Mutil.find_aoe_targets(api, api.get_position(uid), radius, api.mask_enemies(uid))
        if targets.sum() == 0:
            return
        if self.p.restat is not None:
            regen = self.param_value(api, uid, 'regen')
            api.add_dmod(dt, targets, str2stat(self.p.restat), regen)
        if self.p.destat is not None:
            degen = self.param_value(api, uid, 'degen')
            api.add_dmod(dt, targets, str2stat(self.p.destat), -degen)

    @property
    def info(self):
        a = []
        if self.p.restat is not None:
            a.append(f'{self.p.regen} {self.p.restat}')
        if self.p.destat is not None:
            a.append(f'-{self.p.degen} {self.p.destat}')
        a = ' and '.join(a)
        return f'Radiate {a} in a {self.p.radius} radius (per tick).'
