import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import random
import itertools
import numpy as np
import math
from nutil.vars import normalize
from nutil.display import njoin
from engine.common import *
from logic.base import Ability as BaseAbility
from logic.mechanics import Mechanics


class Move(BaseAbility):
    info = 'Move to a target position.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
        'range': 1_000_000,
        'speed': 100,
        'speed_stat': 'air',
        'speed_bonus': 5,
    }
    lore = 'We can all thank Tony the fish for this one.'

    def do_cast(self, api, uid, target):
        speed = self.p.get_speed(api, uid)
        Mechanics.apply_move(api, uid, target=target, move_speed=speed)
        return self.aid


class Attack(BaseAbility):
    info = 'Deal brute damage to a single target.'
    lore = 'A time tested strategy. Use force.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 150,
        'range': 10,
        'damage': 20,
        'damage_stat': 'physical',
        'damage_add': 0.3,
    }

    def do_cast(self, api, uid, target):
        # check range (find target)
        range = self.p.get_range(api, uid)
        target_uid = f = self.find_target(api, uid, target, range, enemy_only=True)
        if isinstance(f, FAIL_RESULT):
            return f

        # get damage percent multiplier from elemental stats
        damage = self.p.get_damage(api, uid)

        # damage effect
        Mechanics.do_brute_damage(api, uid, target_uid, damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color': (0, 0, 0),
        })
        return self.aid


class Barter(BaseAbility):
    info = 'Loot the dead.'
    lore = 'Hello there, corpse. I see your negotiation capabilities have diminished drastically.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
        'range': 0,
        'loot_multi': 1,
    }
    debug = True

    def cast(self, api, uid, target):
        # loot nearest target regardless of check
        range = self.p.get_range(api, uid)
        loot_result, loot_target, loot_pos = Mechanics.apply_loot(api, uid, api.get_position(uid), range)
        # apply loot with bonus if success
        if not isinstance(loot_result, FAIL_RESULT):
            looted_gold = loot_result
            # check cooldown and mana for bonus gold
            if self.check_many(api, uid, checks=self.auto_check) is True:
                self.cost_many(api, uid, costs=self.auto_cost)
                looted_gold *= self.p.get_loot_multi(api, uid)

            # gold income effect
            api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
            self.play_sfx()
            api.add_visual_effect(VisualEffect.SPRITE, 50, params={
                'source': 'coin',
                'point': loot_pos,
                'fade': 50,
                'size': api.units[loot_target].size,
                })
            return self.aid
        return loot_result


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

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.show_stats = ('mana_cost', 'cooldown', 'range', 'stacks', 'duration')

    def do_cast(self, api, uid, target):
        # find target
        if self.p.target == 'self':
            vfx_target = target_uid = uid
        else:
            range = self.p.get_range(api, uid)
            vfx_target = target_uid = f = self.find_target(api, uid, target, range, enemy_only=True)
            if isinstance(f, FAIL_RESULT):
                return f

        # status effect
        status = str2status(self.p.status)
        duration = self.p.get_duration(api, uid)
        stacks = self.p.get_stacks(api, uid)
        Mechanics.apply_debuff(api, target_uid, status, duration, stacks)

        # vfx
        if self.p.target == 'other':
            api.add_visual_effect(VisualEffect.LINE, 5, {
                'p1': api.get_position(uid),
                'p2': api.get_position(target_uid),
                'color': self.color,
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
        if self.p.target == 'self':
            return f'Gain {self.p.status}.'
        elif self.p.target == 'other':
             return f'Apply {self.p.status} to a single target.'
        raise ValueError(f'{self} unknown target type {self.p.target}')


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
        range = self.p.get_range(api, uid)
        target = self.fix_vector(api, uid, target, range)
        # teleport effect
        api.set_position(uid, target)
        api.set_position(uid, target, VALUE.TARGET)
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
        'range': 600,
        'radius': 60,
        'damage': 10,
    }
    auto_check = {'mana', 'cooldown', 'range_point'}
    debug = True

    def do_cast(self, api, uid, target):
        damage = self.p.get_damage(api, uid)
        radius = self.p.get_radius(api, uid)
        targets_mask = self.find_aoe_targets(api, target, radius)
        Mechanics.do_brute_damage(api, uid, targets_mask, damage)

        api.add_visual_effect(VisualEffect.LINE, 10, {
            'p1': api.get_position(uid),
            'p2': target,
            'color': self.color,
        })
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
        'mana_cost': 0,
        'status': None,
        'target_restat': None,  # 'hp', 'earth', etc.
        'regen': 0,
        'target_destat': None,  # 'hp', 'earth', etc.
        'degen': 0,
        'radius': 0,
        'include_self': 0,
        'show_aura': 0,
    }
    auto_check = set()
    auto_cost = set()

    def passive(self, api, uid, dt):
        pos = api.get_position(uid)
        radius = self.p.get_radius(api, uid)
        mask = np.ones(api.unit_count)
        if not self.p.include_self:
            mask[uid] = False
        targets = self.find_aoe_targets(api, pos, radius, mask)
        if self.p.show_aura > 0:
            api.add_visual_effect(VisualEffect.CIRCLE, dt-2, {
                'center': pos,
                'radius': radius,
                'color': (*self.color, self.p.show_aura),
                # 'fade': dt/4,
            })
        if targets.sum() == 0:
            return
        status = self.p.status
        if status is not None:
            status = str2status(status)
            Mechanics.apply_debuff(api, targets, status, dt*2, 1)
        if self.p.target_restat is not None:
            regen = self.p.get_regen(api, uid)
            api.add_dmod(dt*2, targets, str2stat(self.p.target_restat), regen)
        if self.p.target_destat is not None:
            degen = self.p.get_degen(api, uid)
            api.add_dmod(dt*2, targets, str2stat(self.p.target_destat), -degen)

    @property
    def info(self):
        a = []
        if self.p.target_restat is not None:
            a.append(f'+{self.p.target_restat}')
        if self.p.target_destat is not None:
            a.append(f'-{self.p.target_destat}')
        a = ' and '.join(a)
        return f'Radiate {a}.'


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
        api.set_status(slice(None), STATUS.SLOW, 500, 50)
        return self.aid


class Shopkeeper(Buff):
    lore = f'Running a mom and pop shop is tough business.'
    def cast(self, api, uid, target):
        radius = 250
        targets = self.find_aoe_targets(api, api.get_position(uid), radius)
        duration = 120
        stacks = api.get_status(uid, STATUS.SHOP, value_name=STATUS_VALUE.STACKS)
        Mechanics.apply_debuff(api, targets, STATUS.SHOP, duration, stacks)
        return self.aid

    @property
    def info(self):
        return f'Offer wares for sale.'


class MapEditorEraser(BaseAbility):
    info = 'Erase a biome droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        api.mod_api.map.remove_droplet(target)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorToggle(BaseAbility):
    info = 'Erase a biome droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        api.mod_api.map.toggle_droplet(target)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorPalette(BaseAbility):
    info = 'Select a biome for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        biome = api.mod_api.map.find_biome(target)
        api.set_status(uid, STATUS.MAP_EDITOR, 0, biome)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorDroplet(BaseAbility):
    info = 'Place a biome droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        tile = api.get_status(uid, STATUS.MAP_EDITOR, STATUS_VALUE.STACKS)
        api.mod_api.map.add_droplet(tile, target)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


ABILITY_CLASSES = {
    'move': Move,
    'barter': Barter,
    'attack': Attack,
    'buff': Buff,
    'consume': Consume,
    'teleport': Teleport,
    'blast': Blast,
    'midas': Midas,
    'regen aura': RegenAura,
    'shopkeeper': Shopkeeper,
    'test': Test,
    'map_editor_eraser': MapEditorEraser,
    'map_editor_toggle': MapEditorToggle,
    'map_editor_palette': MapEditorPalette,
    'map_editor_droplet': MapEditorDroplet,
}
