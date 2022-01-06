import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import math
import numpy as np
from nutil.vars import normalize, is_floatable
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
    miss_color = (1, 1, 1)
    draft_cost = 100

    def __init__(self, aid, name, color, params,
            draftable=True, draft_cost=None,
            show_stats=None, sfx=None):
        self.aid = aid
        self.name = name
        self.color = self.miss_color = color
        self.draftable = draftable
        if draft_cost is not None:
            self.draft_cost = round(draft_cost)
        self.sfx = self.name if sfx is None else sfx

        for p in params:
            if p not in (*self.defaults.keys(), *self.__defaults.keys()):
                logger.debug(f'Setting up parameter {p} for ability {self.name} not found in defaults')
        self.p = Params({**self.__defaults, **self.defaults, **params})
        if self.debug:
            logger.debug(f'Created ability {self.name} with arguments: {params}. ' \
                     f'Defaults: {self.defaults}')

        self.show_stats = list(show_stats.split(', ')) if show_stats is not None else self.p.params
        self.setup()

    def setup(self):
        pass

    def passive(self, api, uid, dt):
        pass

    def cast(self, api, uid, target):
        f = self.check_many(api, uid, target, checks=self.auto_check)
        if isinstance(f, FAIL_RESULT):
            return f
        if self.debug:
            logger.debug(f'{api.units[uid].name} using {self.name} at {target}')
        r = self.do_cast(api, uid, target)
        if not isinstance(r, FAIL_RESULT):
            self.cost_many(api, uid, self.auto_cost)
            self.play_sfx()
        return r

    def play_sfx(self, volume='sfx', **kwargs):
        Assets.play_sfx('ability', self.sfx, volume=volume, replay=True, **kwargs)

    def do_cast(self, api, uid, target):
        logger.debug(f'{self.name} do_cast not implemented. No effect.')
        return self.aid

    # Cost methods
    def cost_many(self, api, uid, costs=None):
        for cost in costs:
            getattr(self, f'cost_{cost}')(api, uid)

    def cost_cooldown(self, api, uid, cost=None):
        api.set_cooldown(uid, self.aid, self.p.get_cooldown(api, uid) if cost is None else cost)

    def cost_mana(self, api, uid, cost=None):
        api.set_stats(uid, STAT.MANA, -(self.p.get_mana_cost(api, uid) if cost is None else cost), additive=True)

    # Check methods
    def check_many(self, api, uid, target=None, checks=None):
        if checks is None:
            checks = self.auto_check
        for check in checks:
            c = getattr(self, f'check_{check}')
            r = c(api, uid, target)
            if isinstance(r, FAIL_RESULT):
                return r
        return True

    def check_mana(self, api, uid, target=None):
        if api.get_stats(uid, STAT.MANA) < self.p.get_mana_cost(api, uid):
            return FAIL_RESULT.MISSING_COST
        return True

    def check_cooldown(self, api, uid, target=None):
        if api.get_cooldown(uid, self.aid) > 0:
            return FAIL_RESULT.ON_COOLDOWN
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

    def find_aoe_targets(self, api, point, radius, mask=None, alive_only=True):
        dists = api.get_distances(point)
        in_radius = dists < radius
        if mask is not None:
            in_radius = np.logical_and(in_radius, mask)
        if alive_only:
            in_radius = np.logical_and(in_radius, api.mask_alive())
        return in_radius

    # Properties
    @property
    def sprite(self):
        return self.name

    def gui_state(self, api, uid, target=None):
        miss = 0
        cd = api.get_cooldown(uid, self.aid)
        excess_mana = api.get_stats(uid, STAT.MANA) - self.p.mana_cost
        strings = []
        # color = (0, 0.9, 0, 1)
        color = (0, 0, 0, 0)
        if cd > 0:
            strings.append(f'C: {api.ticks2s(cd):.1f}')
            color = (1, 0.3, 0, 1)
            miss += 1
        if excess_mana < 0:
            strings.append(f'M: {-excess_mana:.1f}')
            color = (0, 0, 0.8, 1)
            miss += 1
        if miss > 1:
            color = (0, 0, 0, 1)
        return '\n'.join(strings), color

    @property
    def universal_description(self):
        return '\n'.join([
            f'{self.info}\n',
            self.p.repr_universal(self.show_stats),
            f'\n\n\n{"_"*30}\n\n"{self.lore}"',
            f'\nClass: « {self.__class__.__name__} »',
        ])

    def description(self, api, uid, params=None):
        if params is None:
            params = self.show_stats
        return '\n'.join([
            f'{self.info}\n',
            *(f'{self.p.repr(p, api, uid)}' for p in params),
            # f'\n> {self.lore}',
            # f'\nClass: « {self.__class__.__name__} »',
        ])

    def __repr__(self):
        return f'{self.aid} {self.name}'


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
        formula = ''
        param = self._params[param_name]
        if isinstance(param, ExpandedParam):
            stat_value = api.get_stats(uid, param.stat)
            stat_name = f'{stat_value:.1f} {param.stat.name.lower().capitalize()}'
            formula = self._formula_repr(param_name, stat_name)
            formula = f' ({formula})'
        pval = self._param_value(param_name, api, uid)
        if is_floatable(pval):
            if param_name in self.show_as_time:
                pval = f'{api.ticks2s(pval):.1f} s'
            elif param_name in self.show_as_delta:
                pval = f'{api.s2ticks(pval):.2f}/s'
            else:
                pval = f'{pval:.1f}'
        return f'{self.pname_repr(param_name)}: {pval}{formula}'

    def repr_universal(self, params=None):
        if params is None:
            params = self.params
        return '\n'.join(self.repr_param(p) for p in params)

    def repr_param(self, param_name):
        return f'{self.pname_repr(param_name)}: {self._formula_repr(param_name)}'

    def _formula_repr(self, param_name, stat_name=None):
        param = self._params[param_name]
        if not isinstance(param, ExpandedParam):
            s = str(param)
        else:
            s = f'{param.base}'
            for mod in param.mods:
                stat_name = param.stat.name.lower().capitalize() if stat_name is None else stat_name
                s = mod.cls.repr(s, stat_name, mod.factor)
        return s

    def __expand_base(self, base_name):
        base = self.__raw_params[base_name]
        stat_name = f'{base_name}_stat'
        if stat_name not in self.__raw_params:
            return base
        stat_name = self.__raw_params[stat_name]
        mods = []
        for mod_name, mod_cls in PARAM_MODS.items():
            mod_param = f'{base_name}_{mod_name}'
            if mod_param not in self.__raw_params:
                continue
            factor = self.__raw_params[mod_param]
            mods.append(ExpandedMod(mod_cls, factor))
        assert len(mods) > 0
        return ExpandedParam(base, str2stat(stat_name), mods)

    def _param_value(self, value_name, api=None, uid=None):
        param = self._params[value_name]
        if not isinstance(param, ExpandedParam):
            return param
        if api is None or uid is None:
            return param.base
        stat_value = api.get_stats(uid, param.stat)
        value = param.base
        for mod in param.mods:
            value = mod.cls.calc(value, stat_value, mod.factor)
            # logger.debug(f'Found {value_name} value: {param.base:.1f} -> {value:.1f} (using {stat_value:.1f} {param.stat.name}, {mod.cls.name} factor {mod.factor:.1f})')
        return value

    def __getattr__(self, x):
        if x.startswith('get_'):
            return lambda a, u, n=x[4:]: self._param_value(n, a, u)
        if x in self.params:
            return self._param_value(x)

    @staticmethod
    def pname_repr(p):
        return p.capitalize().replace('_', ' ')


class ModAdd:
    name = 'Add'

    @classmethod
    def calc(cls, base, stat, factor):
        return base + (stat * factor)

    @classmethod
    def repr(cls, base, stat, factor):
        return f'{base} + {factor} × {stat}'


PARAM_MODS = {
    'bonus': ModAdd,
}
