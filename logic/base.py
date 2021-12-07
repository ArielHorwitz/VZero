import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import math
import numpy as np
from nutil.vars import normalize, is_floatable
from engine.common import *
from logic.mechanics import Mechanics


GUI_STATE = collections.namedtuple('GUI_STATE', ('string', 'color'))
MISS_COLOR = (1, 1, 1)


class Ability:
    __defaults = defaults = {'mana_cost': 0, 'cooldown': 0}
    auto_check = {'mana', 'cooldown'}
    auto_cost = {'mana', 'cooldown'}
    info = 'An ability.'
    lore = 'Some people know about this ability.'
    debug = False

    def __init__(self, aid, name, color, params):
        self.aid = aid
        self.name = name
        self.color = color

        for p in params:
            if p not in (*self.defaults.keys(), *self.__defaults.keys()):
                logger.debug(f'Setting up parameter {p} for ability {self.name} not found in defaults')
        self.p = Params({**self.__defaults, **self.defaults, **params})
        if self.debug:
            logger.debug(f'Created ability {self.name} with arguments: {params}. ' \
                     f'Defaults: {self.defaults}')

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
        return r

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
                    'color': MISS_COLOR,
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
                    'color': MISS_COLOR,
                })
            return FAIL_RESULT.OUT_OF_RANGE
        return target_uid

    def mask_enemies(self, api, uid):
        m = np.ones(len(api.units))
        m[uid] = 0
        return m

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
        color = (0, 0.9, 0, 1)
        if cd > 0:
            strings.append(f'CD: {api.ticks2s(cd):.1f}')
            color = (1, 0.3, 0, 1)
            miss += 1
        if excess_mana <= 0:
            strings.append(f'M: {-excess_mana:.1f}')
            color = (0, 0, 0.8, 1)
            miss += 1
        if miss > 1:
            color = (0, 0, 0, 1)
        return GUI_STATE('\n'.join(strings), color)

    @property
    def universal_description(self):
        return '\n'.join([
            f'{self.info}\n',
            f'Class: « {self.__class__.__name__} »',
            self.p.repr_universal,
            f'\n> {self.lore}',
        ])

    def description(self, api, uid):
        return '\n'.join([
            f'{self.info}\n',
            f'Class: « {self.__class__.__name__} »',
            *(f'{self.p.repr(p, api, uid)}' for p in self.p.params),
            f'\n> {self.lore}',
        ])

    def __repr__(self):
        return f'{self.aid} {self.name}'


ExpandedParam = collections.namedtuple('ExpandedParam', ['base', 'stat', 'mods'])
ExpandedMod = collections.namedtuple('ExpandedMod', ['cls', 'factor'])


class Params:
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
            formula = f'\n     = {self._formula_repr(param_name, stat_name)}'
        pval = self._param_value(param_name, api, uid)
        if is_floatable(pval):
            pval = f'{pval:.1f}'
        return f'{self.pname_repr(param_name)}: {pval}{formula}'

    @property
    def repr_universal(self):
        return '\n'.join(self.repr_param(p) for p in self.params)

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


class ModReduction:
    name = 'Reduction'

    @classmethod
    def calc(cls, base, stat, factor):
        return base * Mechanics.diminishing_curve(stat*factor, 50, 20)

    @classmethod
    def repr(cls, base, stat, factor):
        return f'{base} - ({factor} • {stat}) %'


class ModPercent:
    name = 'Percent'

    @classmethod
    def calc(cls, base, stat, factor):
        return base * (1 + (stat * factor / 100))

    @classmethod
    def repr(cls, base, stat, factor):
        return f'{base} + {factor}% × {stat}'


class ModMul:
    name = 'Mul'

    @classmethod
    def calc(cls, base, stat, factor):
        return base * stat * factor

    @classmethod
    def repr(cls, base, stat, factor):
        return f'{base} × {factor} × {stat}'


class ModAdd:
    name = 'Add'

    @classmethod
    def calc(cls, base, stat, factor):
        return base + (stat * factor)

    @classmethod
    def repr(cls, base, stat, factor):
        return f'{base} + {factor} × {stat}'


PARAM_MODS = {
    'reduc': ModReduction,
    'bonus': ModPercent,
    'mul': ModMul,
    'add': ModAdd,
}
