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
    }
    lore = 'We can all thank Tony the fish for this one.'
    auto_check = {'mana', 'cooldown', 'unbounded'}

    def do_cast(self, api, uid, target):
        speed = self.p.get_speed(api, uid) / 100
        range = self.p.get_range(api, uid)
        target = self.fix_vector(api, uid, target, range)
        Mechanics.apply_move(api, uid, target=target, move_speed=speed)
        return self.aid


class Attack(BaseAbility):
    info = 'Hit a single target.'
    lore = 'A time tested strategy. Use force.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 100,
        'range': 10,
        'damage': 0,
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
        Mechanics.do_normal_damage(api, uid, Mechanics.mask(api, target_uid), damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color': (0, 0, 0),
        })
        return self.aid


class PassiveAttack(BaseAbility):
    info = 'Passively hit a single target.'
    lore = 'Sidekicks are the best.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 150,
        'range': 20,
        'damage': 10,
    }

    def passive(self, api, uid, dt):
        f = self.check_many(api, uid)
        if isinstance(f, FAIL_RESULT):
            return f
        target = api.get_position(uid)
        # check range (find target)
        range = self.p.get_range(api, uid)
        target_uid = f = self.find_target(api, uid, target, range, enemy_only=True, draw_miss_vfx=False)
        if isinstance(f, FAIL_RESULT):
            return f

        # get damage percent multiplier from elemental stats
        damage = self.p.get_damage(api, uid)

        # damage effect
        api.set_cooldown(uid, self.aid, self.p.get_cooldown(api, uid))
        Mechanics.do_normal_damage(api, uid, Mechanics.mask(api, target_uid), damage)
        api.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color': (0, 0, 0),
        })
        api.add_visual_effect(VisualEffect.SFX, 5, {
            'sfx': self.sfx,
        })
        return self.aid

    def cast(self, api, uid, target):
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
        loot_result, loot_target = Mechanics.apply_loot(api, uid, api.get_position(uid), range)
        # apply loot with bonus if success
        if not isinstance(loot_result, FAIL_RESULT):
            looted_gold = loot_result
            # check cooldown and mana for bonus gold
            if self.check_many(api, uid, target) is True:
                self.cost_many(api, uid)
                looted_gold *= self.p.get_loot_multi(api, uid)

            # gold income effect
            api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
            self.play_sfx()
            api.add_visual_effect(VisualEffect.SPRITE, 50, params={
                'source': 'coin',
                'point': api.get_position(loot_target),
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
        'vfx_radius': None,
        }
    debug = True

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
        duration = self.p.get_duration(api, uid)
        stacks = self.p.get_stacks(api, uid)
        Mechanics.apply_debuff(api, target_uid, self.__status, duration, stacks)

        # vfx
        if self.p.target == 'other':
            api.add_visual_effect(VisualEffect.LINE, 5, {
                'p1': api.get_position(uid),
                'p2': api.get_position(target_uid),
                'color': self.color,
            })
        if self.p.vfx_radius is not None:
            api.add_visual_effect(VisualEffect.CIRCLE, duration, params={
                'color': (*self.color, 0.4),
                'radius': api.get_stats(vfx_target, STAT.HITBOX)*self.p.vfx_radius,
                'uid': vfx_target,
                'fade': duration*4,
            })
        return self.aid

    def setup(self):
        self.__status = str2status(self.p.status)
        if self.p.target == 'self':
            self.info = f'Gain {self.p.status}.'
        elif self.p.target == 'other':
            self.info = f'Apply {self.p.status} to a single target.'
        else:
            raise ValueError(f'{self} unknown target type: {self.p.target}')


class PassiveBuff(BaseAbility):
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
        'stat': None,
        'scaling': 0,
        'time_factor': 0,
    }

    def passive(self, api, uid, dt):
        amount = self.__scaling * dt
        api.set_stats(uid, self.__stat, amount, additive=True)

    def setup(self):
        self.__scaling = self.p.scaling / 6000
        self.__stat = str2stat(self.p.stat)
        self.info = f'Gain {self.p.scaling:.1f} {self.p.stat} per minute.'


class Teleport(BaseAbility):
    info = 'Instantly teleport to a target position.'
    lore = 'The ancient art of blinking goes back eons.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
        'range': 0,
    }
    auto_check = {'mana', 'cooldown', 'unbounded'}

    def do_cast(self, api, uid, target):
        pos = api.get_position(uid)
        range = self.p.get_range(api, uid) + api.get_stats(uid, STAT.HITBOX)
        target = self.fix_vector(api, uid, target, range)
        # teleport effect
        Mechanics.apply_teleport(api, uid, target)
        api.add_visual_effect(VisualEffect.LINE, 10, {
            'p1': pos, 'p2': target, 'color': self.color})
        return self.aid


class TeleportHome(BaseAbility):
    info = 'Instantly teleport home.'
    lore = 'Home is where the WiFi is.'
    defaults = {
        'mana_cost': 0,
        'cooldown': 0,
    }
    auto_check = {'mana', 'cooldown', 'unbounded'}

    def do_cast(self, api, uid, target):
        pos = api.get_position(uid)
        target = api.units[uid]._respawn_location
        # teleport effect
        Mechanics.apply_teleport(api, uid, target)
        api.add_visual_effect(VisualEffect.LINE, 10, {
            'p1': pos, 'p2': target, 'color': self.color})
        return self.aid


class Blast(BaseAbility):
    info = 'Deal blast damage in an area.'
    lore = 'Level 3 wizard let\'s GOOOO!'
    defaults = {
        'mana_cost': 35,
        'cooldown': 500,
        'range': 600,
        'radius': 60,
        'damage': 10,
    }
    # auto_check = {'mana', 'cooldown', 'range_point'}
    debug = True

    def setup(self):
        self.__fix_vector = 'fix_vector' in self.p.params

    def do_cast(self, api, uid, target):
        range = self.p.get_range(api, uid) + api.get_stats(uid, STAT.HITBOX)
        if self.__fix_vector:
            target = self.fix_vector(api, uid, target, range)
        if api.get_distances(target, uid) > range:
            if uid == 0:
                cast_pos = api.get_position(uid)
                miss_range = range + api.get_stats(uid, STAT.HITBOX)
                miss_vector = normalize(target - cast_pos, miss_range)
                api.add_visual_effect(VisualEffect.LINE, 10, {
                    'p1': cast_pos,
                    'p2': cast_pos + miss_vector,
                    'color': self.miss_color,
                })
            return FAIL_RESULT.OUT_OF_RANGE

        damage = self.p.get_damage(api, uid)
        radius = self.p.get_radius(api, uid)
        targets_mask = self.find_aoe_targets(api, target, radius)
        Mechanics.do_blast_damage(api, uid, targets_mask, damage)

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
        'target': 'enemies',  # 'allies', 'enemies'
        'include_self': 1,
        'restat': None,  # 'hp', 'earth', etc.
        'regen': 0,
        'destat': None,  # 'hp', 'earth', etc.
        'degen': 0,
        'radius': 500,
        'show_aura': 0,
    }
    auto_check = set()
    auto_cost = set()

    def setup(self):
        self.target = self.p.target
        self.include_self = bool(self.p.include_self)
        self.status = str2status(self.p.status) if self.p.status is not None else None
        self.restat = str2stat(self.p.restat) if self.p.restat is not None else None
        self.destat = str2stat(self.p.destat) if self.p.destat is not None else None
        self.show_aura = self.p.show_aura
        a = []
        if self.restat is not None:
            a.append(f'+{self.restat.name.lower()}')
        if self.destat is not None:
            a.append(f'-{self.destat.name.lower()}')
        a = ' and '.join(a)
        self.info = f'Radiate {a}.'

    def passive(self, api, uid, dt):
        pos = api.get_position(uid)
        radius = self.p.get_radius(api, uid)
        mask = self.mask_enemies(api, uid)
        if self.target == 'allies':
            mask = np.invert(mask)
            mask[uid] = self.include_self
        targets = self.find_aoe_targets(api, pos, radius, mask)
        if self.show_aura > 0:
            api.add_visual_effect(VisualEffect.CIRCLE, dt*5, {
                'center': pos,
                'radius': radius,
                'color': (*self.color, self.p.show_aura),
                # 'fade': dt*1000,
            })
        if targets.sum() == 0:
            return
        if self.status is not None:
            Mechanics.apply_debuff(api, targets, self.status, dt*8, 1)
        if self.restat is not None:
            regen = self.p.get_regen(api, uid)
            api.add_dmod(dt*8, targets, self.restat, regen/8)
        if self.destat is not None:
            degen = self.p.get_degen(api, uid)
            api.add_dmod(dt*8, targets, self.destat, -degen/8)


class Shopkeeper(BaseAbility):
    info = 'Offer wares for sale.'
    lore = f'Running a mom and pop shop is tough business.'
    defaults = {
        'radius': 500,
        }

    def passive(self, api, uid, dt):
        radius = self.p.get_radius(api, uid)
        targets = self.find_aoe_targets(api, api.get_position(uid), radius)
        duration = dt*2
        stacks = api.get_status(uid, STATUS.SHOP, value_name=STATUS_VALUE.STACKS)
        Mechanics.apply_debuff(api, targets, STATUS.SHOP, duration, stacks)
        return self.aid


class MapEditorEraser(BaseAbility):
    info = 'Erase a biome droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        api.units[uid].api.map.remove_droplet(target)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorToggle(BaseAbility):
    info = 'Toggle the biome of a droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        api.units[uid].api.map.toggle_droplet(target)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorPipette(BaseAbility):
    info = 'Select a biome for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        biome = api.units[uid].api.map.find_biome(target)
        api.set_status(uid, STATUS.MAP_EDITOR, 0, biome)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorDroplet(BaseAbility):
    info = 'Place a biome droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        tile = api.get_status(uid, STATUS.MAP_EDITOR, STATUS_VALUE.STACKS)
        api.units[uid].api.map.add_droplet(tile, target)
        api.add_visual_effect(VisualEffect.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


ABILITY_CLASSES = {
    'move': Move,
    'barter': Barter,
    'attack': Attack,
    'passive_attack': PassiveAttack,
    'buff': Buff,
    'passive_buff': PassiveBuff,
    'teleport': Teleport,
    'teleport home': TeleportHome,
    'blast': Blast,
    'regen aura': RegenAura,
    'shopkeeper': Shopkeeper,
    'map_editor_eraser': MapEditorEraser,
    'map_editor_toggle': MapEditorToggle,
    'map_editor_pipette': MapEditorPipette,
    'map_editor_droplet': MapEditorDroplet,
}
