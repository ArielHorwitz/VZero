import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import math
import numpy as np
from nutil.vars import normalize, is_floatable, nsign_str, modify_color, try_float, NP, AutoIntEnum
from nutil.random import SEED
from data.load import SubCategory as RDFSubCategory
from data.assets import Assets
from data.settings import Settings
from engine.common import *
from logic.mechanics import Mechanics, Rect
from logic.compat_abilities import ABILITY_CLASSES as COMPAT_ABILITY_CLASSES


PHASE = AutoIntEnum('AbilityPhase', ['PASSIVE', 'ACTIVE', 'ALT'])


class BaseAbility:
    PHASE = PHASE
    info = 'An ability.'
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
        self.sprite = Assets.get_sprite('ability', raw_data.default['sprite'] if 'sprite' in raw_data.default else self.name)
        self.__shared_cooldown_name = raw_data.default['cooldown'] if 'cooldown' in raw_data.default else self.name

        self.phases = {p: Phase(self, p, RDFSubCategory()) for p in PHASE}
        for phase_name, phase_data in raw_data.items():
            if not self.has_phase(phase_name):
                continue
            p = self.s2phase(phase_name)
            self.phases[p] = Phase(self, p, phase_data)
        self.state_phase = self.phases[self.s2phase(raw_data['state']) if 'state' in raw_data.default else PHASE.ACTIVE]

        # Parse effects
        for effect_full_name, effect_data in raw_data.items():
            effect_name_list = effect_full_name.split('.')
            if len(effect_name_list) < 3:
                continue
            phase, condition, etype, *__ = effect_name_list
            if not self.has_phase(phase):
                continue
            phase = self.phases[self.s2phase(phase)]
            condition = Phase.s2cond(condition)
            effect = EFFECT_CLASSES[etype](self, effect_data)
            phase.add_effect(condition, effect)

        logger.info(f'Created ability {self} with data: {raw_data}')

    def off_cooldown(self, api, uid):
        self.passive(api, uid, 0)

    def _setup(self):
        self.cooldown_aid = self.off_cooldown_aid = str2ability(self.__shared_cooldown_name)
        self.fail_sfx = 'no_fail_sfx' not in self._raw_data.default.positional
        self.upcast_sfx = 'no_upcast_sfx' not in self._raw_data.default.positional

    def passive(self, api, uid, dt):
        phase = self.phases[PHASE.PASSIVE]
        phase.apply_effects(api, uid, dt)
        return self.aid

    def active(self, api, uid, target_point, alt=0):
        phase = self.phases[PHASE.ACTIVE if alt == 0 else PHASE.ALT]
        phase.apply_effects(api, uid, dt=0, target_point=target_point, draw_miss=True)
        return self.aid

    @property
    def universal_description(self):
        return self._description()

    def description(self, api, uid):
        return self._description((api, uid))

    def _description(self, au=None):
        s = [
            self.info,
            self.shared_cooldown_repr,
        ]
        for phase in self.phases.values():
            s.extend(phase.description(au))
        return '\n'.join(s)

    def gui_state(self, api, uid):
        cd, missing_mana, status = self.state_phase.check_state(api, uid)
        miss = 0
        strings = []
        color = (0, 0, 0, 0)
        if cd > 0:
            strings.append(f'C: {api.ticks2s(cd):.1f}')
            color = (1, 0, 0, 1)
            miss += 1
        if missing_mana > 0:
            strings.append(f'M: {missing_mana:.1f}')
            color = (0, 0, 1, 1)
            miss += 1
        if miss > 1 or status > 0:
            color = (0, 0, 0, 1)
        return '\n'.join(strings), color

    @property
    def shared_cooldown_repr(self):
        if self.aid != self.cooldown_aid:
            return f'Shares cooldown with: {self.__shared_cooldown_name}'
        return ''

    def play_sfx(self, volume='sfx', replay=True, **kwargs):
        Assets.play_sfx('ability', self.sfx, volume=volume, replay=replay, **kwargs)

    def __repr__(self):
        return f'{self.aid} {self.name}'

    @staticmethod
    def s2phase(s):
        return getattr(PHASE, s.upper())

    @staticmethod
    def has_phase(s):
        return hasattr(PHASE, s.upper())


ABILITY_CLASSES = {
    'base': BaseAbility,
    **COMPAT_ABILITY_CLASSES,
}


class Formula:
    def __init__(self, raw_param):
        self.__raw_param = raw_param

    @property
    def base_value(self):
        return self.__raw_param

    @property
    def repr(self):
        return ''

    @property
    def raw_param(self):
        return self.__raw_param

    def get_value(self, api, uid):
        return self.__raw_param

    def full_str(self, key, nl=True):
        r = self.repr
        if r:
            nl = '\n' if nl else ''
            return f'{nl}{key}{r}'
        return ''


class BonusFormula(Formula):
    def __init__(self, raw_param):
        super().__init__(raw_param)
        base, stat, factor = [_.strip() for _ in raw_param.split(',')]
        self._base = float(base)
        self._stat = str2stat(stat)
        self._factor = float(factor)

    @property
    def base_value(self):
        return self._base

    @property
    def repr(self):
        return f'{self._base} + {self._factor} × [b]{self._stat.name.lower()}[/b]'

    def get_value(self, api, uid):
        return self._base + self._factor * api.get_stats(uid, self._stat)


class ScaleFormula(Formula):
    def __init__(self, raw_param):
        super().__init__(raw_param)
        base, stat, factor, curve = [_.strip() for _ in raw_param.split(', ')]
        self._base = float(base)
        self._stat = str2stat(stat)
        self._factor = float(factor) - self._base
        self._curve = float(curve)

    @property
    def base_value(self):
        return self._base

    @property
    def repr(self):
        return f'{self._base} < [b]{self._stat.name.lower()}[/b] §{self._curve} < {self._factor+self._base}'

    def get_value(self, api, uid):
        stat = api.get_stats(uid, self._stat)
        scale = self._factor * Mechanics.scaling(stat, self._curve, ascending=True)
        return self._base + scale


class ReducFormula(Formula):
    def __init__(self, raw_param):
        super().__init__(raw_param)
        factor, stat, base, curve = [_.strip() for _ in raw_param.split(', ')]
        self._base = float(base)
        self._stat = str2stat(stat)
        self._factor = float(factor) - self._base
        self._curve = float(curve)

    @property
    def base_value(self):
        return self._factor

    @property
    def repr(self):
        return f'{self._factor+self._base} > [b]{self._stat.name.lower()}[/b] §{self._curve} > {self._base}'

    def get_value(self, api, uid):
        stat = api.get_stats(uid, self._stat)
        scale = self._factor * Mechanics.scaling(stat, self._curve, ascending=False)
        return self._base + scale


def resolve_formula(name, raw_data, sentinel=None):
    clsmap = {
        'bonus': BonusFormula,
        'scale': ScaleFormula,
        'reduc': ReducFormula,
    }
    for raw_name, raw_formula in raw_data.items():
        if raw_name == name:
            return Formula(raw_formula)
        if not raw_name.startswith(name):
            continue
        assert '.' in raw_name
        raw_name, raw_pcls = raw_name.split('.')
        if raw_name != name:
            continue
        pcls = clsmap[raw_pcls]
        return pcls(raw_formula)
    if sentinel is None:
        raise CorruptedDataError(f'Failed to find a formula for {name} in {raw_data}')
    return Formula(sentinel)


CONDITION = AutoIntEnum('PhaseCondition', ['UNCONDITIONAL', 'UPCAST', 'DOWNCAST'])
Targets = collections.namedtuple('Targets', ['aid', 'dt', 'fails', 'source', 'point', 'mask', 'area', 'selected'])


class Phase:
    CONDITION = CONDITION

    @classmethod
    def s2cond(cls, s):
        return getattr(CONDITION, s.upper())

    def __init__(self, ability, pid, raw_data):
        self.pid = pid
        self.phase_name = pid.name.lower()
        self.ability = ability
        self.debug = 'debug' in raw_data.positional
        self.auto_fail_sfx = False if 'no_fail_sfx' in raw_data.positional else (self.pid is not PHASE.PASSIVE)
        self.auto_sfx = False if 'no_sfx' in raw_data.positional else (self.pid is not PHASE.PASSIVE)
        self.show_cond = False if 'no_description' in raw_data.positional else True

        # Geometry
        self.point = raw_data['point'] if 'point' in raw_data else 'nofix'
        self.area_shape = raw_data['area'] if 'area' in raw_data else 'none'
        assert self.area_shape in {'none', 'circle', 'rect'}
        self.area = self.area_shape != 'none'
        self.area_radius = resolve_formula('radius', raw_data, sentinel=100)
        self.area_width = resolve_formula('width', raw_data, sentinel=300)
        self.area_length = resolve_formula('length', raw_data, sentinel=200)
        self.offset_include_hitbox = 'disinclude_hitbox' not in raw_data.positional

        # Targetting
        self.target = raw_data['target'] if 'target' in raw_data else 'none'
        assert self.target in {'none', 'self', 'selected', 'other', 'ally', 'enemy', 'neutral'}
        self.targeting_point = self.target == 'none' or self.point == 'self' or 'point_target' in raw_data.positional
        self.single_selection_distance = resolve_formula('selection_distance', raw_data, float('inf'))
        self.range = resolve_formula('range', raw_data, sentinel=float('inf'))
        self.mana_cost = resolve_formula('mana_cost', raw_data, sentinel=0)
        self.cooldown = resolve_formula('cooldown', raw_data, sentinel=0)
        self.status_block = list(str2stat(_.strip()) for _ in raw_data['status_block'].split(", ")) if 'status_block' in raw_data else []
        self.cached_selected = f'{self.ability.aid}-selected'

        self.effects = {
            CONDITION.UNCONDITIONAL: [],
            CONDITION.UPCAST: [],
            CONDITION.DOWNCAST: [],
        }

        if self.debug:
            logger.debug(f'Logging {self.ability} {self.phase_name} debug')

    def apply_effects(self, api, uid, dt, target_point=None, draw_miss=False):
        if not self.has_effect:
            return
        # Collect targets
        if target_point is None:
            target_point = api.get_position(uid)
        targets = self.get_targets(api, uid, target_point, dt, draw_miss)
        # Unconditional effects
        for effect in self.effects[CONDITION.UNCONDITIONAL]:
            effect.apply(api, uid, targets)
        # Conditional (upcast/downcast) effects
        condition = CONDITION.DOWNCAST if targets.fails else CONDITION.UPCAST
        for effect in self.effects[condition]:
            effect.apply(api, uid, targets)
        if self.debug:
            d = ' '.join(str(_) for _ in [
                targets.dt,
                targets.source,
                targets.point,
                np.flatnonzero(targets.mask),
                np.flatnonzero(targets.area),
                np.flatnonzero(targets.selected),
            ])
            logger.debug(f'{self} fails: {targets.fails} {d}')
        # Auto SFX
        if targets.fails:
            if self.auto_fail_sfx:
                fail_sfx = sorted(targets.fails, key=self.sort_fails_key)[0]
                api.logic.play_feedback(fail_sfx, uid)
        else:
            if self.auto_sfx:
                self.ability.play_sfx()

    def add_effect(self, condition, effect):
        self.effects[condition].append(effect)

    def description(self, au=None):
        if not self.has_effect:
            return []
        s = []
        for condition in CONDITION:
            fx = self.effects[condition]
            if len(fx) > 0:
                cond_str = f': {self.repr(au)}' if self.show_cond else ''
                s.append(f'\n[u]{self.phase_name.capitalize()} {condition.name.lower()}[/u]{cond_str}')
                for effect in fx:
                    r = effect.repr(au)
                    if r:
                        s.append(r)
        return s

    def repr(self, au):
        if au:
            range = self.range.get_value(*au)
            cooldown = self.cooldown.get_value(*au)
            mana_cost = self.mana_cost.get_value(*au)
            area_radius = self.area_radius.get_value(*au)
            area_width = self.area_width.get_value(*au)
            area_length = self.area_length.get_value(*au)
        else:
            range = self.range.base_value
            cooldown = self.cooldown.base_value
            mana_cost = self.mana_cost.base_value
            area_radius = self.area_radius.base_value
            area_width = self.area_width.base_value
            area_length = self.area_length.base_value
        target_str = f'[b]Point target[/b]' if self.targeting_point else f'[b]{self.target.capitalize()} target[/b]'
        range_str = f' in [b]{int(range)}[/b] range' if range < 10**6 else ''
        if self.area_shape == 'circle':
            area_str = f'; {self.target} in {area_radius} radius {self.area_shape}'
        elif self.area_shape == 'rect':
            area_str = f'; {self.target} in {area_width} × {area_length} area'
        else:
            area_str = ''
        subs = []
        if range_str:
            subs.append(self.range.full_str('Range: '))
        cost_str = []
        if mana_cost > 0:
            cost_str.append(f'[b]{mana_cost:.1f}[/b] mana')
            subs.append(self.mana_cost.full_str('Mana cost: '))
        if cooldown > 0:
            cost_str.append(f'[b]{cooldown:.2f}[/b]s cooldown')
            subs.append(self.cooldown.full_str('Cooldown: '))
        cost_str = ', '.join(cost_str)
        br = '\nCost: ' if cost_str else ''
        subs = ''.join(subs)
        return f'[i]{target_str}{range_str}{area_str}{br}{cost_str}[/i]{subs}'

    def draw_miss(self, api, uid, **params):
        if uid in api.logic.miss_feedback_uids:
            api.add_visual_effect(VFX.LINE, 15, params=params)

    def get_targets(self, api, uid, target_point, dt=0, draw_miss=True):
        fails = set()
        # Resolve target point
        source_point = api.get_position(uid)
        range = self.range.get_value(api, uid)
        fixed_target_point = unfixed_target_point = target_point
        if self.point == 'self':
            fixed_target_point = target_point = source_point
        elif api.get_distances(target_point, uid) > range:
            hitbox = api.get_stats(uid, STAT.HITBOX)
            fixed_vector = normalize(target_point - source_point, range + hitbox)
            fixed_target_point = source_point + fixed_vector
            if self.point == 'fix':
                unfixed_target_point = target_point
                target_point = fixed_target_point
            if self.targeting_point and self.point != 'fix':
                fails.add(FAIL_RESULT.OUT_OF_RANGE)
                if draw_miss:
                    self.draw_miss(api, uid, p1=source_point, p2=fixed_target_point)

        live_mask = api.get_stats(slice(None), STAT.HP) > 0
        range_mask = api.unit_distance(uid) <= range
        empty_mask = Mechanics.mask(api, [])

        # Resolve selected
        selected = api.units[uid].cache[self.cached_selected]
        if selected is None:
            selected = empty_mask
            if self.target == 'selected':
                fails.add(FAIL_RESULT.MISSING_TARGET)

        # Resolve single and area targets
        single_target_uid = None
        area_uids = []
        available_targets = self.get_allegiance_mask(api, uid) if self.target != 'selected' else selected
        available_targets = available_targets & live_mask
        if available_targets.sum() == 0:
            if not self.targeting_point:
                fails.add(FAIL_RESULT.MISSING_TARGET)
        else:
            subset_uids = np.flatnonzero(available_targets)
            subset_distances = api.get_distances(target_point, subset_uids)
            idx = NP.argmin(subset_distances)
            single_target_uid = subset_uids[idx]
            single_target_dist = subset_distances[idx]
            if single_target_dist > self.single_selection_distance.get_value(api, uid):
                single_target_uid = None
                if not self.targeting_point:
                    fails.add(FAIL_RESULT.MISSING_TARGET)
            else:
                range_distance = api.unit_distance(uid, single_target_uid)
                if not self.targeting_point and range_distance > range:
                    single_target_uid = None
                    fails.add(FAIL_RESULT.OUT_OF_RANGE)
                    if draw_miss:
                        self.draw_miss(api, uid, p1=source_point, p2=fixed_target_point)

            if self.area:
                if not self.targeting_point and single_target_uid:
                    origin = api.get_position(single_target_uid)
                else:
                    origin = target_point
                if self.area_shape == 'circle':
                    radius = self.area_radius.get_value(api, uid)
                    subset_in_radius = api.get_distances(origin, subset_uids) < radius
                    area_uids = subset_uids[np.flatnonzero(subset_in_radius)]
                elif self.area_shape == 'rect':
                    width = self.area_width.get_value(api, uid)
                    length = self.area_length.get_value(api, uid)
                    hb = api.get_stats(subset_uids, STAT.HITBOX)
                    offset = hb[uid] if self.offset_include_hitbox else 0
                    rect = Rect.from_point(source_point, target_point, width, length, offset)
                    subset_pos = api.get_position(np.vstack(subset_uids))
                    subset_in_rect = rect.check_colliding_circles(subset_pos, hb)
                    area_uids = subset_uids[np.flatnonzero(subset_in_rect)]

        single_target_mask = empty_mask if single_target_uid is None else Mechanics.mask(api, single_target_uid)
        area_mask = Mechanics.mask(api, area_uids)

        # Check and pay, mana and cooldown
        if not fails:
            fails |= self.check_pay(api, uid)
        return Targets(self.ability.aid, dt, fails, source_point, target_point, single_target_mask, area_mask, selected)

    def resolve_shape_targets(self, api, uid, shape, origin, args):
        pass

    def get_allegiance_mask(self, api, uid):
        if self.target == 'none':
            return Mechanics.mask(api, [])
        elif self.target == 'self':
            return Mechanics.mask(api, uid)
        else:
            my_allegiance = api.get_stats(uid, STAT.ALLEGIANCE)
            all_allegiances = api.get_stats(slice(None), STAT.ALLEGIANCE)
            if self.target == 'ally':
                mask = (all_allegiances == my_allegiance)
            elif self.target == 'neutral':
                mask = all_allegiances < 0
            elif self.target == 'enemy':
                not_neutral = all_allegiances >= 0
                mask = (all_allegiances != my_allegiance) & not_neutral
            else:
                return Mechanics.mask(api, slice(None))
            mask[uid] = False
            return mask

    def check_pay(self, api, uid):
        fails = set()
        mana_cost = self.mana_cost.get_value(api, uid)
        if api.get_cooldown(uid, self.ability.cooldown_aid) > 0:
            fails.add(FAIL_RESULT.ON_COOLDOWN)
        if api.get_stats(uid, STAT.MANA) < mana_cost:
            fails.add(FAIL_RESULT.MISSING_COST)
        if any(Mechanics.get_status(api, uid, status) > 0 for status in self.status_block):
            fails.add(FAIL_RESULT.OUT_OF_ORDER)
        if not fails:
            cooldown = s2ticks(self.cooldown.get_value(api, uid))
            api.set_cooldown(uid, self.ability.cooldown_aid, cooldown)
            api.set_stats(uid, STAT.MANA, -mana_cost, additive=True)
        return fails

    def check_state(self, api, uid):
        mana = api.get_stats(uid, STAT.MANA)
        mana_cost = self.mana_cost.get_value(api, uid)
        cd = api.get_cooldown(uid, self.ability.cooldown_aid)
        status = any(Mechanics.get_status(api, uid, status_) > 0 for status_ in self.status_block)
        return cd, mana_cost - mana, status

    @property
    def has_effect(self):
        return any([len(self.effects[c]) > 0 for c in CONDITION])

    sorted_fails = [
        FAIL_RESULT.CRITICAL_ERROR,
        FAIL_RESULT.OUT_OF_ORDER,
        FAIL_RESULT.ON_COOLDOWN,
        FAIL_RESULT.MISSING_COST,
        FAIL_RESULT.OUT_OF_BOUNDS,
        FAIL_RESULT.OUT_OF_RANGE,
        FAIL_RESULT.MISSING_TARGET,
        FAIL_RESULT.MISSING_ACTIVE,
        FAIL_RESULT.INACTIVE,
    ]
    @classmethod
    def sort_fails_key(cls, x):
        return cls.sorted_fails.index(x)


class Effect:
    def __init__(self, ability, raw_data):
        pass

    def repr(self, au):
        return ''

    valid_mask_targets = {'self', 'target', 'area', 'selected'}
    valid_point_targets = {'self', 'source', 'point', 'target', 'selected'}
    valid_uid_targets = {'self', 'target', 'selected'}
    @classmethod
    def resolve_target_mask(cls, api, uid, p, targets):
        if p == 'self':
            return uid
        if p == 'target':
            return targets.mask
        if p == 'area':
            return targets.area
        if p == 'selected':
            return targets.selected
        raise ValueError(f'Effect.resolve_target_mask() expecting one of {self.valid_mask_targets}, instead got: {p}')

    @classmethod
    def resolve_target_point(cls, api, uid, p, targets):
        if p == 'self':
            return api.get_position(uid)
        if p == 'source':
            return targets.source
        if p == 'point':
            return targets.point
        if p == 'target':
            if targets.mask.sum() == 0:
                raise RuntimeError(f'Failed to find uids for target {p} from targets {targets}')
            return api.get_position(np.flatnonzero(targets.mask)[0])
        if p == 'selected':
            if targets.selected.sum() == 0:
                raise RuntimeError(f'Failed to find uids for target {p} from targets {targets}')
            return api.get_position(np.flatnonzero(targets.selected)[0])
        raise ValueError(f'Effect.resolve_target_point() expecting one of {self.valid_point_targets}, instead got: {p}')

    @classmethod
    def resolve_target_uid(cls, api, uid, p, targets):
        if p == 'self':
            return uid
        if p == 'target':
            return np.flatnonzero(targets.mask)[0]
        if p == 'selected':
            return np.flatnonzero(targets.selected)[0]
        raise ValueError(f'Effect.resolve_target_uid() expecting one of: {self.valid_uid_targets}; instead got: {p}')

    @classmethod
    def fix_vector(cls, api, uid, target, range):
        pos = api.get_position(uid)
        if np.linalg.norm(pos - target) > range:
            fixed_vector = normalize(target - pos, range)
            target = pos + fixed_vector
        return target


class EffectMove(Effect):
    def __init__(self, ability, raw_data):
        self.speed = resolve_formula('speed', raw_data)
        self.range = resolve_formula('range', raw_data, float('inf'))

    def repr(self, au):
        if au:
            speed = self.speed.get_value(*au)
            range = self.range.get_value(*au)
        else:
            speed = self.speed.base_value
            range = self.range.base_value
        if range < 10**6:
            range_str = f' for [b]{int(range)} units[/b]'
        else:
            range_str = ''
        return f'[u][b]Move[/b] at [b]{speed:.1f} speed[/b]{range_str}[/u]{self.speed.full_str("Speed: ")}{self.range.full_str("Range: ")}'

    def apply(self, api, uid, targets):
        speed = self.speed.get_value(api, uid) / s2ticks(1)
        range = self.range.get_value(api, uid)
        target_point = self.fix_vector(api, uid, targets.point, range)
        Mechanics.apply_move(api, uid, target_point, speed)


class EffectPush(Effect):
    effect_name = 'Push'
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        self.speed = resolve_formula('speed', raw_data, 3)
        self.range = resolve_formula('range', raw_data, 200)

    def repr(self, au):
        if au:
            speed = self.speed.get_value(*au)
            range = self.range.get_value(*au)
        else:
            speed = self.speed.base_value
            range = self.range.base_value
        if range < 0:
            range_str = f' for [b]{int(range)} units[/b]'
        else:
            range_str = ''
        return f'[u][b]{self.effect_name}[/b]{range_str}[/u][/b]{self.range.full_str("Range: ")}{self.speed.full_str("Speed: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        if target_mask.sum() == 0:
            return
        speed = ticks2s(self.speed.get_value(api, uid))
        range = self.range.get_value(api, uid)
        all_pos = api.get_position(target_mask)
        if self.effect_name == 'Push':
            vectors = all_pos - targets.point
        else:
            vectors = targets.point - all_pos
        vsizes = np.linalg.norm(vectors, axis=-1)[:, np.newaxis]
        vsizes[vsizes == 0] = 0.001
        if range == 0:
            range = vsizes
        fixed_vectors = vectors / vsizes * range
        fixed_vector_sizes = np.linalg.norm(fixed_vectors, axis=-1)
        fixed_vectors += all_pos
        durations = fixed_vector_sizes / speed
        target_uids = np.flatnonzero(target_mask)
        unmoveable = api.unmoveable_mask
        for i, tuid in enumerate(target_uids):
            if unmoveable[tuid]:
                continue
            Mechanics.apply_move(api, tuid, fixed_vectors[i], speed)
            Mechanics.apply_debuff(api, tuid, STATUS.BOUNDED, durations[i], 1, reset_move=False)


class EffectPull(EffectPush):
    effect_name = 'Pull'


class EffectLoot(Effect):
    def __init__(self, ability, raw_data):
        self.loot_multi = resolve_formula('loot_multi', raw_data)
        self.range = resolve_formula('range', raw_data)

    def repr(self, au):
        if au:
            loot_multi = self.loot_multi.get_value(*au)
            range = self.range.get_value(*au)
        else:
            loot_multi = self.loot_multi.base_value
            range = self.range.base_value
        if range < 10**6:
            range_str = f' @[b]{int(range)} units[/b]'
        else:
            range_str = ''
        return f'[u][b]Loot[/b] for [b]{int(loot_multi)}%[/b] gold{range_str}[/u]{self.loot_multi.full_str("Loot multi: ")}{self.range.full_str("Range: ")}'

    def apply(self, api, uid, targets):
        range = self.range.get_value(api, uid)
        loot_result, loot_target = Mechanics.apply_loot(api, uid, api.get_position(uid), range)
        if not isinstance(loot_result, FAIL_RESULT):
            loot_multi = self.loot_multi.get_value(api, uid) / 100
            looted_gold = loot_result * loot_multi
            api.set_stats(uid, STAT.GOLD, looted_gold, additive=True)


class EffectTeleport(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'point'

    def repr(self, au):
        return f'[u][b]Teleport[/b][/u]'

    def apply(self, api, uid, targets):
        target_point = self.resolve_target_point(api, uid, self.target, targets)
        Mechanics.apply_teleport(api, uid, target_point)


class EffectTeleportHome(Effect):
    def repr(self, au):
        return '[u][b]Teleport home[/b][/u]'

    def apply(self, api, uid, targets):
        target = api.units[uid]._respawn_location
        Mechanics.apply_teleport(api, uid, targets.point)


class EffectStatus(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        assert self.target in self.valid_mask_targets
        self.status = str2status(raw_data['status'])
        self.stacks = resolve_formula('stacks', raw_data)
        self.stacks_op = raw_data['stacks_op'] if 'stacks_op' in raw_data else None
        self.duration = resolve_formula('duration', raw_data, -1)
        self.duration_op = raw_data['duration_op'] if 'duration_op' in raw_data else None

    def repr(self, au):
        if au:
            stacks = self.stacks.get_value(*au)
            duration = self.duration.get_value(*au)
        else:
            stacks = self.stacks.base_value
            duration = self.duration.base_value
        if self.stacks_op == 'additive':
            stacks_str = f'Add {stacks:.1f}'
        elif self.stacks_op == 'multiplicative':
            stacks_str = f'Add {int(stacks*100)}%'
        else:
            stacks_str = f'Apply {stacks:.1f}'
        duration_str = f' for [b]{duration:.1f}s[/b]' if duration > 0 else ''
        return f'[u][b]{stacks_str} {self.status.name.lower()}[/b]{duration_str}[/u]{self.stacks.full_str("Stacks: ")}{self.duration.full_str("Duration: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        stacks = self.stacks.get_value(api, uid)
        duration = s2ticks(self.duration.get_value(api, uid))
        if duration < 0:
            duration = targets.dt
        if self.stacks_op == 'additive':
            stacks += api.get_status(targets.mask, self.status)
        elif self.stacks_op == 'multiplicative':
            stacks *= api.get_status(targets.mask, self.status)
        if self.duration_op == 'additive':
            duration += max(0, api.get_status(targets.mask, self.status, value_name=STATUS_VALUE.DURATION))
        elif self.duration_op == 'multiplicative':
            duration *= max(0, api.get_status(targets.mask, self.status, value_name=STATUS_VALUE.DURATION))
        Mechanics.apply_debuff(api, target_mask, self.status, duration, stacks, caster=uid)


class EffectStat(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        assert self.target in self.valid_mask_targets
        self.stat = str2stat(raw_data['stat'])
        self.stat_name = self.stat.name.lower()
        self.delta = resolve_formula('delta', raw_data)

    def repr(self, au):
        delta = self.delta.get_value(*au) if au else self.delta.base_value
        stat_str = f'Gain {delta}' if delta >= 0 else f'Lose {delta}'
        return f'[u][b]{stat_str} {self.stat_name}[/b][/u]{self.delta.full_str("Delta: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        delta = self.delta.get_value(api, uid)
        api.set_stats(target_mask, self.stat, delta, additive=True)


class EffectSteal(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        assert self.target in self.valid_mask_targets
        self.stat = str2stat(raw_data['stat'])
        self.stat_name = self.stat.name.lower()
        self.delta = resolve_formula('delta', raw_data)

    def repr(self, au):
        delta = self.delta.get_value(*au) if au else self.delta.base_value
        stat_str = f'Steal {delta}' if delta >= 0 else f'Give {delta}'
        return f'[u][b]{stat_str} {self.stat_name}[/b][/u]{self.delta.full_str("Delta: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        delta = self.delta.get_value(api, uid)
        pre_sub = api.get_stats(target_mask, self.stat)
        api.set_stats(target_mask, self.stat, -delta, additive=True)
        post_sub = api.get_stats(target_mask, self.stat)
        stolen = pre_sub - post_sub
        api.set_stats(uid, self.stat, stolen, additive=True)


class EffectRegen(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        assert self.target in self.valid_mask_targets
        self.stat = str2stat(raw_data['stat'])
        self.stat_name = self.stat.name.lower()
        self.delta = resolve_formula('delta', raw_data)
        self.duration = resolve_formula('duration', raw_data, -1)

    def repr(self, au):
        if au:
            delta = self.delta.get_value(*au)
            duration = self.duration.get_value(*au)
        else:
            delta = self.delta.base_value
            duration = self.duration.base_value
        regen_str = f'Regen {delta}' if delta >= 0 else f'Degen {delta}'
        duration_str = f' for [b]{duration:.1f}s[/b]' if duration > 0 else ''
        return f'[u][b]{regen_str} {self.stat_name}[/b]{duration_str}[/u]{self.delta.full_str("Delta: ")}{self.duration.full_str("Duration: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        delta = ticks2s(self.delta.get_value(api, uid))
        duration = s2ticks(self.duration.get_value(api, uid))
        if duration < 0:
            duration = targets.dt
        Mechanics.apply_regen(api, target_mask, self.stat, duration, delta)


class EffectHit(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        assert self.target in self.valid_mask_targets
        self.damage = resolve_formula('damage', raw_data)

    def repr(self, au):
        damage = self.damage.get_value(*au) if au else self.damage.base_value
        return f'[u][b]Hit[/b] for [b]{damage:.1f} normal[/b] damage[/u]{self.damage.full_str("Damage: ")}'

    def apply(self, api, uid, targets):
        damage = self.damage.get_value(api, uid)
        mask = self.resolve_target_mask(api, uid, self.target, targets)
        Mechanics.do_normal_damage(api, uid, mask, damage)


class EffectBlast(Effect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'area'
        assert self.target in self.valid_mask_targets
        self.damage = resolve_formula('damage', raw_data)

    def repr(self, au):
        damage = self.damage.get_value(*au) if au else self.damage.base_value
        return f'[u][b]Blast[/b] for [b]{damage:.1f} normal[/b] damage[/u]{self.damage.full_str("Damage: ")}'

    def apply(self, api, uid, targets):
        damage = self.damage.get_value(api, uid)
        mask = self.resolve_target_mask(api, uid, self.target, targets)
        Mechanics.do_blast_damage(api, uid, mask, damage)


class EffectSelect(Effect):
    def repr(self, au):
        return 'Select a target'

    dismissable_fails = {
        FAIL_RESULT.MISSING_TARGET,
        FAIL_RESULT.OUT_OF_RANGE,
        FAIL_RESULT.OUT_OF_BOUNDS,
    }
    def apply(self, api, uid, targets):
        if targets.fails & self.dismissable_fails:
            return
        api.units[uid].cache[f'{targets.aid}-selected'] = targets.mask


class EffectUnselect(EffectSelect):
    def repr(self, au):
        return 'Unselect a target'

    dismissable_fails = {
        FAIL_RESULT.MISSING_TARGET,
        FAIL_RESULT.OUT_OF_RANGE,
        FAIL_RESULT.OUT_OF_BOUNDS,
    }
    def apply(self, api, uid, targets):
        if targets.fails & self.dismissable_fails:
            return
        api.units[uid].cache[f'{targets.aid}-selected'] = targets.mask


class EffectShowSelect(EffectSelect):
    def __init__(self, ability, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'target'
        assert self.target in self.valid_uid_targets
        self.play_sfx = 'no_sfx' not in raw_data.positional

    def repr(self, au):
        return ''

    def apply(self, api, uid, targets):
        if targets.fails & self.dismissable_fails:
            return
        target_uid = self.resolve_target_uid(api, uid, self.target, targets)
        play_sfx = self.play_sfx and (uid in api.logic.sfx_feedback_uids)
        api.logic.draw_unit_selection(target_uid, play_sfx=play_sfx)


class EffectSFX(Effect):
    def __init__(self, ability, raw_data):
        self.category = raw_data['category'] if 'category' in raw_data else 'ability'
        self.sfx = raw_data['sfx'] if 'sfx' in raw_data else ability.sfx
        self.volume =  resolve_formula('volume', raw_data, 1)
        self.__volume = Settings.get_volume('sfx')

    def apply(self, api, uid, targets):
        Assets.play_sfx(self.category, self.sfx, volume=self.__volume * self.volume.get_value(api, uid))


class EffectVFXFlash(Effect):
    def __init__(self, ability, raw_data):
        color = str2color(raw_data['color']) if 'color' in raw_data else ability.color
        self.color = self.color = modify_color(color, a=0.15)
        self.duration = raw_data['duration'] if 'duration' in raw_data else 200

    def apply(self, api, uid, targets):
        api.add_visual_effect(VFX.BACKGROUND, self.duration, {'color': self.color})


class EffectVFXLine(Effect):
    def __init__(self, ability, raw_data):
        self.width = raw_data['width'] if 'width' in raw_data else 2
        self.color = str2color(raw_data['color']) if 'color' in raw_data else ability.color
        self.duration = raw_data['duration'] if 'duration' in raw_data else 15
        self.p1 = raw_data['p1']
        self.p2 = raw_data['p2']
        assert self.p1 in self.valid_point_targets and self.p2 in self.valid_point_targets

    def apply(self, api, uid, targets):
        p1, p2 = (self.resolve_target_point(api, uid, p, targets) for p in (self.p1, self.p2))
        api.add_visual_effect(VFX.LINE, self.duration, {
            'color': self.color, 'width': self.width,
            'p1': p1, 'p2': p2,
        })


class EffectVFXCircle(Effect):
    def __init__(self, ability, raw_data):
        self.duration = raw_data['duration'] if 'duration' in raw_data else 100
        self.fade = {'fade': raw_data['fade']} if 'fade' in raw_data else {}
        self.radius = raw_data['radius']
        self.color = str2color(raw_data['color']) if 'color' in raw_data else ability.color
        self.center = raw_data['center']
        assert self.center in self.valid_point_targets
        self.center_key = 'uid' if self.center in self.valid_uid_targets else 'center'
        self.resolve_method = self.resolve_target_uid if self.center_key == 'uid' else self.resolve_target_point

    def apply(self, api, uid, targets):
        api.add_visual_effect(VFX.CIRCLE, self.duration, {
            self.center_key: self.resolve_method(api, uid, self.center, targets),
            'radius': self.radius,
            'color': self.color,
            **self.fade,
        })


class EffectVFXRect(Effect):
    def __init__(self, ability, raw_data):
        self.duration = raw_data['duration'] if 'duration' in raw_data else 100
        self.fade = {'fade': raw_data['fade']} if 'fade' in raw_data else {}
        self.color = str2color(raw_data['color']) if 'color' in raw_data else ability.color
        self.origin = raw_data['origin']
        assert self.origin in self.valid_point_targets
        self.direction_vector = raw_data['direction'] if 'direction' in raw_data else 'point'
        assert self.direction_vector in self.valid_point_targets
        self.length = resolve_formula('length', raw_data, 750)
        self.width = resolve_formula('width', raw_data, 250)
        self.include_hitbox = 'disinclude_hitbox' not in raw_data.positional

    def apply(self, api, uid, targets):
        origin = self.resolve_target_point(api, uid, self.origin, targets)
        target = self.resolve_target_point(api, uid, self.direction_vector, targets)
        length = self.length.get_value(api, uid)
        width = self.width.get_value(api, uid)
        offset = api.get_stats(uid, STAT.HITBOX) if self.include_hitbox else 0
        rect = Rect.from_point(origin, target, width, length, offset)

        points = rect.points
        api.add_visual_effect(VFX.QUAD, self.duration, {
            'points': points,
            'color': self.color,
            **self.fade,
        })


class EffectVFXSprite(Effect):
    def __init__(self, ability, raw_data):
        self.duration = raw_data['duration'] if 'duration' in raw_data else 100
        self.category = raw_data['category'] if 'category' in raw_data else 'ability'
        self.sprite = raw_data['sprite']
        self.fade = {'fade': raw_data['fade']} if 'fade' in raw_data else {}
        self.sizex = raw_data['size']
        self.sizey = raw_data['size_y'] if 'size_y' in raw_data else self.sizex
        self.color = str2color(raw_data['color']) if 'color' in raw_data else ability.color
        self.center = raw_data['center']
        assert self.center in self.valid_point_targets
        self.center_key = 'uid' if self.center in self.valid_uid_targets else 'center'
        self.resolve_method = self.resolve_target_uid if self.center_key == 'uid' else self.resolve_target_point

    def apply(self, api, uid, targets):
        api.add_visual_effect(VFX.SPRITE, self.duration, {
            'category': self.category,
            'source': self.sprite,
            self.center_key: self.resolve_method(api, uid, self.center, targets),
            'size': (self.sizex, self.sizey),
            'color': self.color,
            **self.fade,
        })


class EffectRecast(Effect):
    def __init__(self, ability, raw_data):
        self.ability = ability

    def repr(self, au):
        return f'Cast the passive phase'

    def apply(self, api, uid, targets):
        self.ability.passive(api, uid, 0)


EFFECT_CLASSES = {
    'recast': EffectRecast,
    'vfx-flash': EffectVFXFlash,
    'vfx-line': EffectVFXLine,
    'vfx-circle': EffectVFXCircle,
    'vfx-rect': EffectVFXRect,
    'vfx-sprite': EffectVFXSprite,
    'sfx': EffectSFX,
    'select': EffectSelect,
    'show_select': EffectShowSelect,
    'move': EffectMove,
    'teleport': EffectTeleport,
    'teleport_home': EffectTeleportHome,
    'loot': EffectLoot,
    'status': EffectStatus,
    'hit': EffectHit,
    'blast': EffectBlast,
    'stat': EffectStat,
    'steal': EffectSteal,
    'regen': EffectRegen,
    'push': EffectPush,
    'pull': EffectPull,
}
