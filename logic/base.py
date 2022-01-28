import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import math
import numpy as np
from nutil.vars import normalize, is_floatable, nsign_str
from data.assets import Assets
from engine.common import *
from logic.mechanics import Mechanics


class Ability:
    __defaults = defaults = {'mana_cost': 0, 'cooldown': 0}
    auto_check = {'mana', 'cooldown'}
    auto_cost = {'mana', 'cooldown'}
    info = 'An ability.'
    lore = 'Some people know about this ability.'
    debug = False
    color = 0.5, 0.5, 0.5
    draft_cost = 100

    def __init__(self, aid, name, raw_data):
        self.aid = aid
        self.name = name
        self.debug = 'debug' in raw_data.default.positional
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
        logger.info(f'Created ability {self.name} with arguments: {raw_data.default}. Stats: {raw_stats}. Defaults: {self.defaults}')

    def _setup(self):
        self.shared_cooldown_aid = str2ability(self.__shared_cooldown_name)
        self.setup()

    def setup(self):
        pass

    def passive(self, api, uid, dt):
        pass

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
        api.set_cooldown(uid, self.shared_cooldown_aid, self.p.get_cooldown(api, uid))

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
        if api.get_cooldown(uid, self.shared_cooldown_aid) > 0:
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
                api.add_visual_effect(VisualEffect.LINE, 10, {
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
                api.add_visual_effect(VisualEffect.LINE, 10, {
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
        cd = api.get_cooldown(uid, self.shared_cooldown_aid)
        excess_mana = api.get_stats(uid, STAT.MANA) - self.p.get_mana_cost(api, uid)
        strings = []
        color = (0, 0, 0, 0)
        if cd > 0:
            strings.append(f'C: {api.ticks2s(cd):.1f}')
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
        if self.aid != self.shared_cooldown_aid:
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
                pval = f'{round(api.ticks2s(pval), 2)} s'
            elif param_name in self.show_as_delta:
                pval = f'{round(api.s2ticks(pval), 2)}/s'
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
