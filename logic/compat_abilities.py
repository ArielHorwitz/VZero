import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import random
import itertools
import numpy as np
import math
from data.load import SubCategory as RDFSubCategory
from data.assets import Assets
from data.settings import Settings
from nutil.random import SEED
from nutil.vars import normalize, is_floatable, nsign_str, modify_color
from nutil.display import njoin
from logic.mechanics import Mechanics
from engine.common import *


class BaseAbility:
    __defaults = defaults = {'mana_cost': 0, 'cooldown': 0}
    auto_check = {'mana', 'cooldown'}
    auto_cost = {'mana', 'cooldown'}
    info = 'An ability.'
    lore = 'Some people know about this ability.'
    debug = False
    color = 0.5, 0.5, 0.5
    draft_cost = 100

    def __init__(self, aid, name, raw_data):
        self._raw_data = raw_data
        self.aid = aid
        self.name = name
        self.debug = 'debug' in raw_data.default.positional
        self.info = raw_data.default['info'] if 'info' in raw_data.default else self.info
        self.info = '\n'.join(raw_data['info'].positional) if 'info' in raw_data else self.info
        self.color = self.miss_color = str2color(raw_data.default['color']) if 'color' in raw_data.default else self.color
        self.draftable = False if 'hidden' in raw_data.default.positional else True
        self.draft_cost = round(raw_data.default['draft_cost'] if 'draft_cost' in raw_data.default else self.draft_cost)
        self.sfx = raw_data.default['sfx'] if 'sfx' in raw_data.default else self.name
        self.sfx_grand = raw_data.default['sfx_grand'] if 'sfx_grand' in raw_data.default else self.name
        self.sprite = Assets.get_sprite('ability', raw_data.default['sprite'] if 'sprite' in raw_data.default else self.name)
        self.__shared_cooldown_name = raw_data.default['cooldown'] if 'cooldown' in raw_data.default else self.name
        raw_stats = raw_data['stats'] if 'stats' in raw_data else {}
        for p in raw_stats:
            if p not in (*self.defaults.keys(), *self.__defaults.keys()):
                logger.debug(f'Setting up parameter {p} for ability {self.name} not found in defaults')
        self.p = Params({**self.__defaults, **self.defaults, **raw_stats})

        show_stats = raw_data.default['show_stats'] if 'show_stats' in raw_data.default else None
        self.show_stats = list(show_stats.split(', ')) if show_stats is not None else self.p.params
        logger.info(f'Created ability {self.name} with arguments: {raw_data.default}. Stats: {raw_stats}. Defaults: {self.defaults}.')

    def _setup(self):
        self.cooldown_aid = self.off_cooldown_aid = str2ability(self.__shared_cooldown_name)
        self.setup()

    def setup(self):
        pass

    def load_on_unit(self, api, uid):
        pass

    def unload_from_unit(self, api, uid):
        pass

    def off_cooldown(self, api, uid):
        pass

    def passive(self, api, uid, dt):
        pass

    def active(self, api, uid, target, alt=0):
        return self.cast(api, uid, target)

    def cast(self, api, uid, target):
        f = self.check_many(api, uid, target)
        if isinstance(f, FAIL_RESULT):
            return f
        if self.debug:
            logger.debug(f'{api.units[uid].name} using {self.name} at {target}')
        r = self.do_cast(api, uid, target)
        if not isinstance(r, FAIL_RESULT):
            self.cost_many(api, uid)
            self.play_sfx()
        return r

    def play_sfx(self, volume='sfx', grand=False, **kwargs):
        Assets.play_sfx(
            'ability', self.sfx_grand if grand else self.sfx,
            volume=volume, replay=True, **kwargs)

    def do_cast(self, api, uid, target):
        logger.debug(f'{self.name} do_cast not implemented. No effect.')
        return self.aid

    # Cost methods
    def cost_many(self, api, uid):
        for cost in self.auto_cost:
            getattr(self, f'cost_{cost}')(api, uid)

    def cost_cooldown(self, api, uid):
        api.set_cooldown(uid, self.cooldown_aid, self.p.get_cooldown(api, uid))

    def cost_mana(self, api, uid):
        api.set_stats(uid, STAT.MANA, -self.p.get_mana_cost(api, uid), additive=True)

    # Check methods
    def check_many(self, api, uid, target, checks=None):
        checks = self.auto_check if checks is None else checks
        for check in checks:
            c = getattr(self, f'check_{check}')
            r = c(api, uid, target)
            if isinstance(r, FAIL_RESULT):
                return r
        return True

    def check_mana(self, api, uid, target):
        if api.get_stats(uid, STAT.MANA) < self.p.get_mana_cost(api, uid):
            return FAIL_RESULT.MISSING_COST
        return True

    def check_cooldown(self, api, uid, target):
        if api.get_cooldown(uid, self.cooldown_aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
        return True

    def check_unbounded(self, api, uid, target):
        if Mechanics.get_status(api, uid, STAT.BOUNDED) > 0:
            return FAIL_RESULT.OUT_OF_ORDER
        return True

    def check_range_point(self, api, uid, target_point, draw_miss_vfx=True):
        range = self.p.range
        if api.get_distances(target_point, uid) > range:
            if draw_miss_vfx and uid == 0:
                cast_pos = api.get_position(uid)
                miss_range = range + api.get_stats(uid, STAT.HITBOX)
                miss_vector = normalize(target_point - cast_pos, miss_range)
                api.add_visual_effect(VFX.LINE, 10, {
                    'p1': cast_pos,
                    'p2': cast_pos + miss_vector,
                    'color': self.miss_color,
                })
            return FAIL_RESULT.OUT_OF_RANGE
        return True

    # Utilities
    def fix_vector(self, api, uid, target, range):
        pos = api.get_position(uid)
        if math.dist(pos, target) > range:
            fixed_vector = normalize(target - pos, range)
            target = pos + fixed_vector
        return target

    def find_target(self, api, uid, target_point,
            range=None, draw_miss_vfx=True,
            mask=None, enemy_only=True, alive_only=True,
        ):
        if range is None:
            range = float('inf')
        mask_ = self.mask_enemies(api, uid) if enemy_only else np.ones(len(api.units))
        if mask is not None:
            mask_ = np.logical_and(mask_, mask)
        target_uid, dist = api.nearest_uid(target_point, mask=mask_, alive_only=alive_only)
        if target_uid is None:
            return FAIL_RESULT.MISSING_TARGET

        if api.unit_distance(uid, target_uid) > range:
            if draw_miss_vfx and uid == 0:
                attack_pos = api.get_position(uid)
                target_pos = api.get_position(target_uid)
                miss_range = range + api.get_stats(uid, STAT.HITBOX)
                miss_vector = normalize(target_pos - attack_pos, miss_range)
                api.add_visual_effect(VFX.LINE, 10, {
                    'p1': attack_pos,
                    'p2': attack_pos + miss_vector,
                    'color': self.miss_color,
                })
            return FAIL_RESULT.OUT_OF_RANGE
        return target_uid

    def mask_enemies(self, api, uid):
        my_allegiance = api.get_stats(uid, STAT.ALLEGIANCE)
        all_allegiances = api.get_stats(slice(None), STAT.ALLEGIANCE)
        not_neutral = all_allegiances >= 0
        return (all_allegiances != my_allegiance) & not_neutral

    def mask_allies(self, api, uid):
        my_allegiance = api.get_stats(uid, STAT.ALLEGIANCE)
        all_allegiances = api.get_stats(slice(None), STAT.ALLEGIANCE)
        return all_allegiances == my_allegiance

    def find_aoe_targets(self, api, point, radius, mask=None, alive_only=True):
        dists = api.get_distances(point)
        in_radius = dists < radius
        if mask is not None:
            in_radius = in_radius & mask
        if alive_only:
            in_radius = in_radius & api.mask_alive()
        return in_radius

    def find_aura_targets(self, api, uid, radius, mask=None, alive_only=True):
        dists = api.unit_distance(uid)
        in_radius = dists < radius
        if mask is not None:
            in_radius = in_radius & mask
        if alive_only:
            in_radius = in_radius & api.mask_alive()
        return in_radius

    # Properties
    def gui_state(self, api, uid, target=None):
        miss = 0
        cd = api.get_cooldown(uid, self.cooldown_aid)
        excess_mana = api.get_stats(uid, STAT.MANA) - self.p.get_mana_cost(api, uid)
        strings = []
        color = (0, 0, 0, 0)
        if cd > 0:
            strings.append(f'C: {ticks2s(cd):.1f}')
            color = (1, 0, 0, 1)
            miss += 1
        if excess_mana < 0:
            strings.append(f'M: {-excess_mana:.1f}')
            color = (0, 0, 1, 1)
            miss += 1
        remaining_checks = self.auto_check - {'mana', 'cooldown'}
        f = self.check_many(api, uid, target, remaining_checks)
        if miss > 1 or isinstance(f, FAIL_RESULT):
            color = (0, 0, 0, 1)
        return '\n'.join(strings), color

    @property
    def universal_description(self):
        return '\n'.join([
            f'{self.info}',
            self.shared_cooldown_repr,
            self.p.repr_universal(self.show_stats),
            f'\n\n\n{"_"*30}\n\n"{self.lore}"',
            f'\nClass: « {self.__class__.__name__} »',
        ])

    def description(self, api, uid, params=None):
        if params is None:
            params = self.show_stats
        return '\n'.join([
            f'{self.info}',
            self.shared_cooldown_repr,
            *(f'{self.p.repr(p, api, uid)}' for p in params),
        ])

    def __repr__(self):
        return f'{self.aid} {self.name}'

    @property
    def shared_cooldown_repr(self):
        if self.aid != self.cooldown_aid:
            return f'Shares cooldown with: {self.__shared_cooldown_name}'
        return ''


ExpandedParam = collections.namedtuple('ExpandedParam', ['base', 'stat', 'mods'])
ExpandedMod = collections.namedtuple('ExpandedMod', ['cls', 'factor'])


class Params:
    show_as_time = {'cooldown', 'duration'}
    show_as_delta = {'regen', 'degen'}

    def __init__(self, *args, **kwargs):
        self.__raw_params = dict(*args, **kwargs)
        self._params = {}
        self.params = []
        for base_name, v in self.__raw_params.items():
            # skip any non-base parameter, or anything with an equivalent internal name
            if any([base_name.endswith(f'_{suf}') for suf in ['stat', *PARAM_MODS.keys()]]):
                continue
            if getattr(self, base_name) is not None:
                logger.warning(f'Skipping ability parameter {base_name}, as it overwrites internal name.')
                continue
            self._params[base_name] = self.__expand_base(base_name)
            self.params.append(base_name)

    def repr(self, param_name, api, uid):
        pval = self._param_value(param_name, api, uid)
        if is_floatable(pval):
            if param_name in self.show_as_time:
                pval = f'{round(ticks2s(pval), 2)} s'
            elif param_name in self.show_as_delta:
                pval = f'{round(s2ticks(pval), 2)}/s'
            else:
                pval = f'{round(pval, 2)}'
        return self.repr_param(param_name, pval)

    def repr_universal(self, params=None):
        if params is None:
            params = self.params
        return '\n'.join(self.repr_param(p) for p in params)

    def repr_param(self, param_name, value=None):
        param = self._params[param_name]
        if isinstance(param, ExpandedParam):
            expanded_formula = self._formula_repr(param_name)
            value = '' if value is None else f' [b][i]{value}[/i][/b] -'
            value_str = f'{value} scales with [b]{param.stat.name.lower()}[/b]'
            formula = f'{value_str}\n{expanded_formula}'
        else:
            formula = f' [b][i]{param if value is None else value}[/i][/b]'
        return f'[b]{self.pname_repr(param_name)}:[/b]{formula}'

    def _formula_repr(self, param_name):
        param = self._params[param_name]
        if not isinstance(param, ExpandedParam):
            return str(param)
        else:
            if param.mods:
                s = []
                for mod in param.mods:
                    stat_name = f'{param.stat.name[0].upper()}'
                    s.append(mod.cls.repr(param.base, stat_name, mod.factor))
                return ''.join(s)
            else:
                return str(param.base)

    def __expand_base(self, base_name):
        base = self.__raw_params[base_name]
        mods = []
        for mod_name, mod_cls in PARAM_MODS.items():
            mod_param = f'{base_name}_{mod_name}'
            if mod_param not in self.__raw_params:
                continue
            factor = self.__raw_params[mod_param]
            mods.append(ExpandedMod(mod_cls, factor))
        if len(mods) > 0:
            return ExpandedParam(base, str2stat(base), mods)
        else:
            return base

    def _param_value(self, value_name, api=None, uid=None):
        param = self._params[value_name]
        if not isinstance(param, ExpandedParam):
            return param
        if api is None or uid is None:
            return param.base
        stat_value = api.get_stats(uid, param.stat)
        final_value = 0
        curve = 50
        for mod in param.mods:
            final_value, curve = mod.cls.calc(final_value, curve, stat_value, mod.factor)
        return final_value

    def __getattr__(self, x):
        if x.startswith('get_'):
            return lambda a, u, n=x[4:]: self._param_value(n, a, u)
        if x in self.params:
            return self._param_value(x)

    @staticmethod
    def pname_repr(p):
        return p.capitalize().replace('_', ' ')


class ModBase:
    name = 'Base'
    @classmethod
    def calc(cls, final_value, curve, stat, factor):
        return final_value + factor, curve

    @classmethod
    def repr(cls, base, stat, factor):
        return f' {factor}'


class ModRed:
    name = 'Reduction'

    @classmethod
    def calc(cls, final_value, curve, stat, factor):
        return final_value + factor*Mechanics.scaling(stat, curve), curve

    @classmethod
    def repr(cls, base, stat, factor):
        return f' + {factor}§/{stat}'


class ModScale:
    name = 'Scaling'

    @classmethod
    def calc(cls, final_value, curve, stat, factor):
        return final_value + factor*(1-Mechanics.scaling(stat, curve)), curve

    @classmethod
    def repr(cls, base, stat, factor):
        return f' + {factor}§×{stat}'


class ModCurve:
    name = 'Scaling curve'

    @classmethod
    def calc(cls, final_value, curve, stat, factor):
        return final_value, factor

    @classmethod
    def repr(cls, base, stat, factor):
        return f' (•§{factor})'


class ModAdd(ModBase):
    name = 'Add'

    @classmethod
    def repr(cls, base, stat, factor):
        return f' {nsign_str(factor)}'


class ModBonus:
    name = 'Bonus'

    @classmethod
    def calc(cls, final_value, curve, stat, factor,):
        return final_value + (stat * factor), curve

    @classmethod
    def repr(cls, base, stat, factor):
        return f' {nsign_str(factor)}×{stat}'


PARAM_MODS = {
    'base': ModBase,
    'curve': ModCurve,
    'reduc': ModRed,
    'scale': ModScale,
    'add': ModAdd,
    'bonus': ModBonus,
}


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
        api.add_visual_effect(VFX.LINE, 5, {
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
        f = self.check_many(api, uid, api.get_position(uid))
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
        api.add_visual_effect(VFX.LINE, 5, {
            'p1': api.get_position(uid),
            'p2': api.get_position(target_uid),
            'color': (0, 0, 0),
        })
        api.add_visual_effect(VFX.SFX, 5, {
            'sfx': self.sfx,
        })
        return self.aid

    def cast(self, api, uid, target):
        return self.aid


class Loot(BaseAbility):
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
            grand_sfx = False
            if self.check_many(api, uid, target) is True:
                self.cost_many(api, uid)
                looted_gold *= self.p.get_loot_multi(api, uid)
                grand_sfx = True

            # gold income effect
            api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)
            self.play_sfx(grand=grand_sfx)
            api.add_visual_effect(VFX.SPRITE, 50, params={
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
        Mechanics.apply_debuff(api, Mechanics.mask(api, target_uid), self.__status, duration, stacks, caster=uid)

        # vfx
        if self.p.target == 'other':
            api.add_visual_effect(VFX.LINE, 5, {
                'p1': api.get_position(uid),
                'p2': api.get_position(target_uid),
                'color': self.color,
            })
        if self.p.vfx_radius is not None:
            api.add_visual_effect(VFX.CIRCLE, duration, params={
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
        api.add_visual_effect(VFX.LINE, 10, {
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
        api.add_visual_effect(VFX.LINE, 10, {
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
                api.add_visual_effect(VFX.LINE, 10, {
                    'p1': cast_pos,
                    'p2': cast_pos + miss_vector,
                    'color': self.miss_color,
                })
            return FAIL_RESULT.OUT_OF_RANGE

        damage = self.p.get_damage(api, uid)
        radius = self.p.get_radius(api, uid)
        targets_mask = self.find_aoe_targets(api, target, radius)
        Mechanics.do_blast_damage(api, uid, targets_mask, damage)

        api.add_visual_effect(VFX.LINE, 10, {
            'p1': api.get_position(uid),
            'p2': target,
            'color': self.color,
        })
        api.add_visual_effect(VFX.CIRCLE, 30, {
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
        if self.target == 'allies':
            mask = self.mask_allies(api, uid)
            mask[uid] = self.include_self
        else:
            mask = self.mask_enemies(api, uid)
        targets = self.find_aura_targets(api, uid, radius, mask)
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
        api.add_visual_effect(VFX.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorToggle(BaseAbility):
    info = 'Toggle the biome of a droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        api.units[uid].api.map.toggle_droplet(target)
        api.add_visual_effect(VFX.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorPipette(BaseAbility):
    info = 'Select a biome for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        biome = api.units[uid].api.map.find_biome(target)
        api.set_status(uid, STATUS.MAP_EDITOR, 0, biome)
        api.add_visual_effect(VFX.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


class MapEditorDroplet(BaseAbility):
    info = 'Place a biome droplet for map editing.'
    lore = ''

    def do_cast(self, api, uid, target):
        tile = api.get_status(uid, STATUS.MAP_EDITOR, STATUS_VALUE.STACKS)
        api.units[uid].api.map.add_droplet(tile, target)
        api.add_visual_effect(VFX.SFX, 10, params={'category': 'ui', 'sfx': 'select'})
        return self.aid


ABILITY_CLASSES = {
    'move': Move,
    'loot': Loot,
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
