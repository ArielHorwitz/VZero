import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import random
import itertools
import numpy as np
import math
from nutil.vars import normalize
from nutil.display import njoin
from logic.mechanics.common import *
from logic.mechanics import import_mod_module as import_
BaseAbility = import_('abilities.ability').Ability
Mechanics = import_('mechanics.mechanics').Mechanics
Mutil = import_('mechanics.utilities').Utilities
ITEM = import_('items.items').ITEM
str2item = import_('items.items').str2item


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
        'cooldown': 0,
        'range': 0,
        'loot_multi': 1,
    }
    debug = True

    def cast(self, api, uid, target):
        # loot nearest target regardless of check
        range = self.param_value(api, uid, 'range')
        loot_result, loot_target = Mechanics.apply_loot(api, uid, api.get_position(uid), range)
        # apply loot with bonus if success
        if not isinstance(loot_result, FAIL_RESULT):
            looted_gold = loot_result
            # check cooldown and mana for bonus gold
            if self.check_many(api, uid, checks=self.auto_check) is True:
                self.cost_many(api, uid, costs=self.auto_cost)
                looted_gold *= self.param_value(api, uid, 'loot_multi')

            # gold income effect
            api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
            api.add_visual_effect(VisualEffect.SPRITE, 50, params={
                'source': 'coin',
                'point': api.get_position(loot_target),
                'fade': 50,
                'size': (25, 25),
                })
            return self.aid

        # otherwise, shop
        buy_result = Mechanics.do_buy_shop(api, uid)
        if isinstance(buy_result, FAIL_RESULT):
            # returning loot result always, a more important feedback for the player
            return loot_result
        return self.aid


class Buff(BaseAbility):
    defaults = {
        'status': None,
        'target': 'self',  # 'self' or 'other'
        'mana_cost': 0,
        'cooldown': 0,
        'range': 0,
        'stacks': 0,
        'duration': 0,
        }
    debug = True

    def do_cast(self, api, uid, target):
        # find target
        if self.p.target == 'self':
            vfx_target = target_uid = uid
        else:
            range = self.param_value(api, uid, 'range')
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
            'color': (*self.color, 0.4),
            'radius': api.get_stats(vfx_target, STAT.HITBOX)*1.2,
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
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
        'range': 0,
    }
    debug = True

    def do_cast(self, api, uid, target):
        pos = api.get_position(uid)
        range = self.param_value(api, uid, 'range')
        target = self.fix_vector(api, uid, target, range)
        # teleport effect
        api.set_position(uid, target)
        api.set_position(uid, target, VALUE.TARGET_VALUE)
        api.add_visual_effect(VisualEffect.LINE, 10, {
            'p1': pos,
            'p2': target,
            'color': self.color,
        })
        return self.aid


class Blast(BaseAbility):
    info = 'Deal brute damage in an area.'
    lore = 'Level 3 wizard let\'s GOOOO!'
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
            'color': (*self.color, 0.5),
            'fade': 30,
        })
        return self.aid


class RegenAura(BaseAbility):
    lore = 'Bright and dark mages are known for their healing and life draining abilities.'
    defaults = {
        'restat': None,  # 'hp', 'earth', etc.
        'regen': 0,
        'destat': None,  # 'hp', 'earth', etc.
        'degen': 0,
        'radius': 0,
        'show_aura': 0,
    }
    auto_check = set()
    auto_cost = set()

    def passive(self, api, uid, dt):
        pos = api.get_position(uid)
        radius = self.param_value(api, uid, 'radius')
        targets = Mutil.find_aoe_targets(api, pos, radius, api.mask_enemies(uid))
        if self.p.show_aura > 0:
            api.add_visual_effect(VisualEffect.CIRCLE, dt-2, {
                'center': pos,
                'radius': radius,
                'color': (*self.color, self.p.show_aura),
                # 'fade': dt/4,
            })
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


class Midas(BaseAbility):
    defaults = {
        'gold': 0,
    }

    def passive(self, api, uid):
        api.set_stats(uid, STAT.GOLD, self.p.gold, additive=True)
        return self.aid


class Test(BaseAbility):
    info = 'Developer experimental stuff.'
    lore = 'Don\'t ask.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
    }
    debug = True

    def do_cast(self, api, uid, target):
        item = random.choice(list(ITEM))
        api.set_status(uid, STATUS.SHOP, 1_000_000, item)
        return self.aid


class Shopkeeper(Buff):
    def cast(self, api, uid, target):
        radius = 50
        targets = Mutil.find_aoe_targets(api, api.get_position(uid), radius)
        duration = 120
        stacks = api.get_status(uid, STATUS.SHOP, value_name=STATUS_VALUE.STACKS)
        Mechanics.apply_debuff(api, targets, STATUS.SHOP, duration, stacks)
        return self.aid
