import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import math
from nutil.vars import normalize, modify_color, is_floatable
from nutil.display import njoin
from logic.mechanics.common import *
from logic.mechanics.ability import Ability as BaseAbility, GUI_STATE
from logic.mechanics import import_mod_module as import_
Mutil = import_('mechanics.utilities').Utilities


class Ability(BaseAbility):
    defaults = {'mana_cost': 0, 'cooldown': 0}
    auto_check = {'mana', 'cooldown'}
    auto_cost = {'mana', 'cooldown'}
    info = 'An ability.'
    lore = 'Some people know about this ability.'
    debug = False

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

    def check_range_target_enemy(self, api, uid, target_point):
        range = None
        if 'range' in self.p:
            range = self.p.range + api.get_stats(uid, STAT.HITBOX)
        target_uid = f = mutil.find_target_enemy(api, uid, target_point, range=range)
        if isinstance(target_uid, FAIL_RESULT):
            return f
        return True

    def check_range_point(self, api, uid, target_point):
        range = self.p.range + api.get_stats(uid, STAT.HITBOX)
        if math.dist(api.get_position(uid), target_point) > range:
            return FAIL_RESULT.OUT_OF_RANGE
        return True

    # Utilities
    def fix_vector(self, api, uid, target, range):
        pos = api.get_position(uid)
        if math.dist(pos, target) > range:
            fixed_vector = normalize(target - pos, range)
            target = pos + fixed_vector
        return target

    # Parameters
    def setup(self, **params):
        if self.defaults is None:
            logger.error(f'{self.__class__} missing defaults')
            self.defaults = {}
        for k, v in params.items():
            if k == 'color':
                if hasattr(COLOR, v.upper()):
                    self.color = getattr(COLOR, v.upper())
                else:
                    rgb = tuple(float(_) for _ in v.split(', '))
                    assert len(rgb) == 3
                    self.color = rgb
            if k not in tuple(self.defaults.keys()):
                logger.debug(f'Setting up parameter {k} for ability {self.name} but no existing default')
        self.p = Params({**self.defaults, **params})
        logger.debug(f'Created ability {self.name} with arguments: {params}. ' \
                     f'Defaults: {self.defaults}')

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

    # Properties
    def gui_state(self, api, uid, target=None):
        cd = api.get_cooldown(uid, self.aid)
        excess_mana = api.get_stats(uid, STAT.MANA) - self.p.mana_cost
        strings = []
        color = self.color
        if cd > 0:
            strings.append(f'CD: {api.ticks2s(cd):.1f}')
            color = modify_color(self.color, v=0.25)
        if excess_mana <= 0:
            strings.append(f'M: {-excess_mana:.1f}')
            color = modify_color(self.color, v=0.25)
        return GUI_STATE(', '.join(strings), color)

    @property
    def general_description(self):
        return '\n'.join([
            f'{self.info}\n',
            f'Class: « {self.__class__.__name__} »',
            *(self.p.repr_universal(p) for p in self.p.params),
            f'\n> {self.lore}',
        ])

    def description(self, api, uid):
        return '\n'.join([
            f'{self.info}\n',
            f'Class: « {self.__class__.__name__} »',
            *(f'{self.p.repr(p, api, uid)}' for p in self.p.params),
            f'\n> {self.lore}',
        ])


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
            formula = f'   = {self._formula_repr(param_name, stat_name)}'
        pval = self._param_value(param_name, api, uid)
        if is_floatable(pval):
            pval = f'{pval:.1f}'
        return f'{self.pname_repr(param_name)}: {pval}{formula}'

    def repr_universal(self, param_name):
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
        return base * Mutil.diminishing_curve(stat*factor, 50, 20)

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
