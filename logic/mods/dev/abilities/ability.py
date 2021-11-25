import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import math
from nutil.vars import normalize, modify_color
from nutil.display import njoin
from logic.mechanics.common import *
from logic.mechanics.ability import Ability as BaseAbility, GUI_STATE
from logic.mechanics import import_mod_module as import_
Mutil = import_('mechanics.utilities').Utilities


class Ability(BaseAbility):
    defaults = {'mana_cost': 0, 'cooldown': 10}
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
        api.set_cooldown(uid, self.aid, self.param_value(api, uid, 'cooldown') if cost is None else cost)

    def cost_mana(self, api, uid, cost=None):
        api.set_stats(uid, STAT.MANA, -(self.param_value(api, uid, 'mana_cost') if cost is None else cost), additive=True)

    # Check methods
    def check_many(self, api, uid, target=None, checks=None):
        for check in checks:
            c = getattr(self, f'check_{check}')
            r = c(api, uid, target)
            if isinstance(r, FAIL_RESULT):
                return r
        return True

    def check_mana(self, api, uid, target=None):
        if api.get_stats(uid, STAT.MANA) < self.p.mana_cost:
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

    # Parameter values
    def param_value(self, api, uid, value_name):
        param_name = f'{value_name}_stat'
        if param_name not in self.p:
            return self.p[value_name]
        stat_value = api.get_stats(uid, str2stat(self.p[param_name]))
        for s, f in STAT_MODS.items():
            factor = f'{value_name}_{s}'
            if factor in self.p:
                value = f(self.p[value_name], stat_value, self.p[factor])
                if self.debug:
                    logger.debug(f'{self.name} found {value_name} value: {self.p[value_name]} -> {value} (using {s}, factor {self.p[factor]})')
        return value

    # Utilities
    def fix_vector(self, api, uid, target, range):
        pos = api.get_position(uid)
        if math.dist(pos, target) > range:
            fixed_vector = normalize(target - pos, range)
            target = pos + fixed_vector
        return target

    # Parameters
    def setup(self, **params):
        for k, v in params.items():
            if k == 'color':
                if hasattr(COLOR, v.upper()):
                    self.color = getattr(COLOR, v.upper())
                else:
                    rgb = tuple(float(_) for _ in v.split(', '))
                    assert len(rgb) == 3
                    self.color = rgb
            if k not in tuple(self.defaults.keys()):
                logger.info(f'Setting up parameter {k} for ability {self.name} but no existing default')
        if self.defaults is None:
            logger.error(f'{self.__class__} missing defaults')
            self.defaults = {}
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
    def description(self):
        return njoin([
            f'{self.info}\n\n{self.lore}\n',
            f'< Class: {self.__class__.__name__} >',
            *(f'{k}: {v}' for k, v in self.p.items()),
        ])


class Params(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, x):
        logger.debug(f'Trying to retrieve: {x} from:\n{self}')
        return self[x]


class StatMods:
    @classmethod
    def reduction(cls, base, stat, factor):
        return base * Mutil.diminishing_curve(stat*factor, 50, 20)

    @classmethod
    def bonus_percent(cls, base, stat, factor):
        return base * (1 + (stat * factor / 100))

    @classmethod
    def mul(cls, base, stat, factor):
        return base * stat * factor

    @classmethod
    def add(cls, base, stat, factor):
        return base + (stat * factor)


STAT_MODS = {
    'reduc': StatMods.reduction,  # Multiply by diminishing curve, e.g. for cooldown reduction
    'bonus': StatMods.bonus_percent,  # Add a percentage bonus
    'mul': StatMods.mul,  # Multiply by factor
    'add': StatMods.add,  # Flat addition
}
