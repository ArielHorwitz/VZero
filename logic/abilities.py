import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import enum
import collections
import math
import numpy as np
from nutil.vars import normalize, is_floatable, nsign_str, modify_color, try_float, NP, AutoIntEnum, is_iterable
from nutil.random import SEED
from data.load import SubCategory as RDFSubCategory
from data.assets import Assets
from data.settings import Settings
from engine.common import *
from logic.mechanics import Mechanics, Rect


PHASE = AutoIntEnum('AbilityPhase', ['PASSIVE', 'ACTIVE', 'ALT'])
CONDITION = AutoIntEnum('PhaseCondition', ['UNCONDITIONAL', 'UPCAST', 'DOWNCAST'])
Targets = collections.namedtuple('Targets', ['aid', 'dt', 'fails', 'source', 'point', 'single', 'area', 'selected'])


class BaseAbility:
    PHASE = PHASE
    info = ''
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
        if not self.draftable:
            self.color = 1, 1, 1
        self.draft_cost = round(raw_data.default['draft_cost'] if 'draft_cost' in raw_data.default else self.draft_cost)
        self.sfx = raw_data.default['sfx'] if 'sfx' in raw_data.default else self.name
        self.sprite = Assets.get_sprite('ability', raw_data.default['sprite'] if 'sprite' in raw_data.default else self.name)
        self.__shared_cooldown_name = raw_data.default['cooldown'] if 'cooldown' in raw_data.default else self.name

        self.stats = self._parse_stats(raw_data['stats'] if 'stats' in raw_data else RDFSubCategory())
        self.phases = {p: Phase(self, p, RDFSubCategory()) for p in PHASE}
        for phase_name, phase_data in raw_data.items():
            if not self.has_phase(phase_name):
                continue
            p = self.s2phase(phase_name)
            self.phases[p] = Phase(self, p, phase_data)
        self.state_phase = self.phases[self.s2phase(raw_data['state']) if 'state' in raw_data.default else PHASE.ACTIVE]
        self.off_cooldown_phase = self.s2phase(raw_data.default['off_cooldown']) if 'off_cooldown' in raw_data.default else None
        self.cached_selected_key = f'{self}-selected'

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
            effect = EFFECT_CLASSES[etype](phase, effect_data)
            phase.add_effect(condition, effect)

        logger.info(f'Created ability {self} with data: {raw_data}')

    def balance_stats(self, api, uid):
        if not self.stats:
            return
        unit = api.units[uid]
        for i, (stat, value, formula) in enumerate(self.stats):
            pre_bonus = unit.cache[f'{self}-stats'][i][2]
            target = formula.get_value(api, uid)
            if value is VALUE.DELTA:
                target = ticks2s(target)
            delta = target - pre_bonus
            if delta == 0:
                continue
            pre_stat = api.get_stats(uid, stat, value)
            api.set_stats(uid, stat, delta, value, additive=True)
            post_stat = api.get_stats(uid, stat, value)
            actual_delta = round(post_stat - pre_stat, 4)
            unit.cache[f'{self}-stats'][i][2] += actual_delta

    def remove_stats(self, api, uid):
        if not self.stats:
            return
        unit = api.units[uid]
        for s, v, bonus in unit.cache[f'{self}-stats']:
            api.set_stats(uid, s, -bonus, value_name=v, additive=True)
        unit.cache[f'{self}-stats'] = None

    @staticmethod
    def _parse_stats(raw_data):
        stats = []
        for raw_key, raw_value in raw_data.items():
            raw_statval = raw_key
            if '=' in raw_key:
                raw_statval, formula_name = raw_key.split('=')
            try:
                stat, statval = str2statvalue(raw_statval)
            except Exception as e:
                raise CorruptedDataError(f'Failed to recognize ability passive bonus stat: \'{raw_statval}\'')
            formula = resolve_formula(raw_statval, {raw_key: raw_value})
            stats.append((stat, statval, formula))
        return stats

    def off_cooldown(self, api, uid):
        if self.off_cooldown_phase is PHASE.PASSIVE:
            self.passive(api, uid, 0)
        elif self.off_cooldown_phase is PHASE.ACTIVE:
            self.active(api, uid, None)
        elif self.off_cooldown_phase is PHASE.ALT:
            self.active(api, uid, None, 1)

    def load_on_unit(self, api, uid):
        unit = api.units[uid]
        if unit.cache[f'{self}-loadcount'] is not None:
            unit.cache[f'{self}-loadcount'] += 1
            return
        unit.cache[f'{self}-loadcount'] = 1
        unit.cache[f'{self}-stats'] = [[s, v, 0] for s,v,f in self.stats]

    def unload_from_unit(self, api, uid):
        unit = api.units[uid]
        loadcount = unit.cache[f'{self}-loadcount']
        if loadcount == 0:
            logger.warning(f'{self} requested to unload but found loadcount 0')
        unit.cache[f'{self}-loadcount'] = None if loadcount <= 1 else loadcount - 1
        self.remove_stats(api, uid)

    def _setup(self):
        self.cooldown_aid = self.off_cooldown_aid = str2ability(self.__shared_cooldown_name)
        self.fail_sfx = 'no_fail_sfx' not in self._raw_data.default.positional
        self.upcast_sfx = 'no_upcast_sfx' not in self._raw_data.default.positional

    def passive(self, api, uid, dt):
        self.balance_stats(api, uid)
        phase = self.phases[PHASE.PASSIVE]
        phase.apply_effects(api, uid, dt)
        return self.aid

    def active(self, api, uid, target_point, alt=0):
        phase = self.phases[PHASE.ACTIVE if alt == 0 else PHASE.ALT]
        phase.apply_effects(api, uid, dt=0, target_point=target_point)
        return self.aid

    @property
    def universal_description(self):
        return self._description()

    def description(self, api, uid):
        return self._description((api, uid))

    def stats_str(self, au):
        strs = []
        for s, v, f in self.stats:
            name = stat_name = s.name.lower().capitalize()
            name = f'{stat_name}'
            value = f.value_repr(au)
            if v is VALUE.MAX:
                name = f'Max {stat_name}'
            elif v is VALUE.MIN:
                name = f'Min {stat_name}'
            elif v is VALUE.DELTA:
                name = f'{stat_name} /s'
            elif v is VALUE.TARGET:
                name = f'Target {stat_name}'
            strs.append(f'[b]{name}:[/b] {value}')
        return '\n'.join(strs)

    def _description(self, au=None):
        s = []
        if self.info:
            s.append(self.info)
        if self.stats:
            s.append(f'\n[u]Passive stat bonus:[/u]\n{self.stats_str(au)}')
        s.append('_'*30)
        if self.aid != self.cooldown_aid:
            s.append(f'Shares cooldown with: {self.__shared_cooldown_name}')
        for phase in self.phases.values():
            s.extend(phase.description(au))
        sr = self.selected_repr(au)
        if sr:
            s.append(f'\nSelected: {sr}')
        return '\n'.join(s)

    def gui_state(self, api, uid):
        cd, missing_mana, other_fail = self.state_phase.check_state(api, uid)
        miss = 0
        strings = []
        color = (0, 0, 0, 0)
        if cd > 0:
            strings.append(f'C: {round(ticks2s(cd), 1)}')
            color = (1, 0, 0, 1)
            miss += 1
        if missing_mana > 0:
            strings.append(f'M: {round(missing_mana, 1)}')
            color = (0, 0, 1, 1)
            miss += 1
        if miss > 1 or other_fail > 0:
            color = (0, 0, 0, 1)
        return '\n'.join(strings), color

    @property
    def shared_cooldown_repr(self):
        if self.aid != self.cooldown_aid:
            return
        return ''

    def cache_selected(self, api, uid):
        return api.units[uid].cache[self.cached_selected_key]

    def selected_repr(self, au):
        if au is None:
            return None
        api, uid = au
        cs = self.cache_selected(api, uid)
        if cs is None:
            return None
        uids = np.flatnonzero(cs)
        extra = f', +{len(uids)-3}' if len(uids) > 3 else ''
        return ', '.join([api.units[u].name for u in uids[:3]]) + extra

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
}


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
        self.show_miss = False if 'no_miss_vfx' in raw_data.positional or self.pid is PHASE.PASSIVE else True

        # Geometry
        self.point = raw_data['point'] if 'point' in raw_data else 'nofix'
        self.area_shape = raw_data['area'] if 'area' in raw_data else 'none'
        assert self.area_shape in {'none', 'circle', 'rect'}
        self.area = self.area_shape != 'none'
        self.area_radius = resolve_formula('radius', raw_data, sentinel=100)
        self.area_width = resolve_formula('width', raw_data, sentinel=300)
        self.area_length = resolve_formula('length', raw_data, sentinel=200)
        self.include_hitbox = 'include_hitbox' in raw_data.positional

        # Targetting
        self.requires_los = 'requires_los' in raw_data.positional
        self.target = raw_data['target'] if 'target' in raw_data else 'none'
        assert self.target in {'none', 'self', 'selected', 'other', 'ally', 'enemy', 'neutral'}
        self.include_self = 'include_self' in raw_data.positional
        self.targeting_point = self.target == 'none' or 'point_target' in raw_data.positional  #  or self.point == 'self'
        self.single_selection_distance = resolve_formula('selection_distance', raw_data, float('inf'))
        self.range = resolve_formula('range', raw_data, sentinel=float('inf'))
        self.mana_cost = resolve_formula('mana_cost', raw_data, sentinel=0)
        self.cooldown = resolve_formula('cooldown', raw_data, sentinel=0)
        self.stat_block = list(str2stat(_.strip()) for _ in raw_data['status_block'].split(", ")) if 'status_block' in raw_data else []
        self.stat_require = list(str2stat(_.strip()) for _ in raw_data['status_require'].split(", ")) if 'status_require' in raw_data else []

        self.effects = {
            CONDITION.UNCONDITIONAL: [],
            CONDITION.UPCAST: [],
            CONDITION.DOWNCAST: [],
        }

        if self.debug:
            logger.info(f'Logging {self.ability} {self.phase_name} debug')

    def __repr__(self):
        return f'<{self.ability.name} {self.ability.aid} {self.phase_name} phase>'

    def apply_effects(self, api, uid, dt, target_point=None):
        if not self.has_effect:
            return
        if target_point is None:
            target_point = api.get_position(uid)
        target_point = Mechanics.bound_to_map(api.logic, target_point)
        # Collect targets
        targets = self.get_targets(api, uid, target_point, dt)
        if self.debug:
            d = ' '.join(str(_) for _ in [
                'fails:', targets.fails,
                'dt:', targets.dt,
                'source:', targets.source,
                'point:', targets.point,
                'single:', np.flatnonzero(targets.single),
                'area:', np.flatnonzero(targets.area),
                'selected:', np.flatnonzero(targets.selected),
            ])
            target_str = f'point{"*" if self.targeting_point else ""}: {self.point} target{"" if self.targeting_point else "*"}: {self.target} '
            logger.info(f'Tick: {api.tick}, {self} found: {target_str} {d}')
        # Unconditional effects
        for effect in self.effects[CONDITION.UNCONDITIONAL]:
            effect.apply(api, uid, targets)
        # Conditional (upcast/downcast) effects
        condition = CONDITION.DOWNCAST if targets.fails else CONDITION.UPCAST
        for effect in self.effects[condition]:
            effect.apply(api, uid, targets)
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
                cond_str = f': {self.repr(au)}' if condition is CONDITION.UPCAST else ''
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
        subs = []
        if self.area_shape == 'circle':
            area_str = f'; {self.target} in [b]{int(area_radius)} radius[/b] {self.area_shape}'
            subs.append(self.area_radius.full_str('Radius: '))
        elif self.area_shape == 'rect':
            area_str = f'; {self.target} in [b]{int(area_width)} × {int(area_length)}[/b] area'
            subs.append(self.area_width.full_str('Width: '))
            subs.append(self.area_length.full_str('Length: '))
        else:
            area_str = ''
        if range_str:
            subs.append(self.range.full_str('Range: '))
        cost_str = []
        if mana_cost > 0:
            cost_str.append(f'[b]{round(mana_cost, 1)}[/b] mana')
            subs.append(self.mana_cost.full_str('Mana cost: '))
        if cooldown > 0:
            cost_str.append(f'[b]{round(cooldown, 2)}[/b]s cooldown')
            subs.append(self.cooldown.full_str('Cooldown: '))
        cost_str = ', '.join(cost_str)
        cost_str = f'; {cost_str}' if cost_str else ''
        if self.stat_block:
            subs.append(f'\nBlocked by: [b]{", ".join(_.name.lower() for _ in self.stat_block)}[/b]')
        if self.stat_require:
            subs.append(f'\nRequires: [b]{", ".join(_.name.lower() for _ in self.stat_require)}[/b]')
        if self.requires_los:
            target_str = f'{target_str} (requires line of sight)'
        subs = ''.join(subs)
        return f'[i]{target_str}{range_str}{area_str}{cost_str}[/i]{subs}'

    def draw_miss(self, api, uid, **params):
        if uid in api.logic.miss_feedback_uids:
            api.add_visual_effect(VFX.LINE, 15, params=params)

    def get_targets(self, api, uid, target_point, dt=0):
        fails = set()
        # Resolve target point
        source_point = api.get_position(uid)
        range = unfixed_range = self.range.get_value(api, uid)
        if self.requires_los:
            range = min(range, api.units[uid].view_distance)
        fixed_target_point = unfixed_target_point = target_point
        if self.point == 'self':
            fixed_target_point = target_point = source_point
        elif api.get_distances(target_point, uid) > range:
            hitbox = Mechanics.get_stats(api, uid, STAT.HITBOX)
            fixed_vector = normalize(target_point - source_point, range + hitbox)
            fixed_target_point = source_point + fixed_vector
            if self.point == 'fix':
                unfixed_target_point = target_point
                target_point = fixed_target_point
            if self.targeting_point and self.point != 'fix':
                fails.add(FAIL_RESULT.OUT_OF_RANGE)
                if self.show_miss:
                    self.draw_miss(api, uid, p1=source_point, p2=fixed_target_point)

        live_mask = api.get_stats(slice(None), STAT.HP) > 0
        range_mask = api.unit_distance(uid) <= range
        empty_mask = Mechanics.mask(api, [])

        # Resolve selected
        selected = self.ability.cache_selected(api, uid)
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
                    if self.show_miss:
                        single_target_vector = api.get_positions(single_target_uid) - source_point
                        miss_point = source_point + normalize(single_target_vector, range + Mechanics.get_stats(api, uid, STAT.HITBOX))
                        self.draw_miss(api, uid, p1=source_point, p2=miss_point)
                    single_target_uid = None
                    fails.add(FAIL_RESULT.OUT_OF_RANGE)

            if self.area:
                if not self.targeting_point and single_target_uid:
                    origin = api.get_position(single_target_uid)
                else:
                    origin = target_point
                if self.area_shape == 'circle':
                    radius = self.area_radius.get_value(api, uid)
                    if self.include_hitbox:
                        radius += Mechanics.get_stats(api, uid, STAT.HITBOX)
                    subset_in_radius = api.get_distances(origin, subset_uids) < radius
                    area_uids = subset_uids[np.flatnonzero(subset_in_radius)]
                elif self.area_shape == 'rect':
                    width = self.area_width.get_value(api, uid)
                    length = self.area_length.get_value(api, uid)
                    hb_radius = api.get_stats(subset_uids, STAT.HITBOX)
                    offset = hb_radius[uid] if self.include_hitbox else 0
                    rect = Rect.from_point(source_point, target_point, width, length, offset)
                    subset_pos = api.get_position(np.vstack(subset_uids))
                    subset_in_rect = rect.check_colliding_circles(subset_pos, hb_radius)
                    area_uids = subset_uids[np.flatnonzero(subset_in_rect)]

        single_target_mask = empty_mask if single_target_uid is None else Mechanics.mask(api, single_target_uid)
        area_mask = Mechanics.mask(api, area_uids)

        # Check and pay, mana and cooldown
        if not fails:
            fails |= self.check_pay(api, uid)
        return Targets(self.ability.aid, dt, fails, source_point, target_point, single_target_mask, area_mask, selected)

    def get_allegiance_mask(self, api, uid):
        if self.target == 'none':
            return Mechanics.mask(api)
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
                mask = Mechanics.mask(api, slice(None))
            mask[uid] = self.include_self
            return mask

    def check_pay(self, api, uid):
        fails = set()
        mana_cost = self.mana_cost.get_value(api, uid)
        if api.get_cooldown(uid, self.ability.cooldown_aid) > 0:
            fails.add(FAIL_RESULT.ON_COOLDOWN)
        if api.get_stats(uid, STAT.MANA) < mana_cost:
            fails.add(FAIL_RESULT.MISSING_COST)
        if any(Mechanics.get_stats(api, uid, stat) > 0 for stat in self.stat_block):
            fails.add(FAIL_RESULT.OUT_OF_ORDER)
        if any(Mechanics.get_stats(api, uid, stat) <= 0 for stat in self.stat_require):
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
        status_block = any(Mechanics.get_stats(api, uid, status_) > 0 for status_ in self.stat_block)
        status_lacking = any(Mechanics.get_stats(api, uid, status_) <= 0 for status_ in self.stat_require)
        other_fail = status_block or status_lacking
        return cd, mana_cost - mana, other_fail

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


class SentinelValue:
    pass


def resolve_formula(name, raw_data, sentinel=SentinelValue):
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
        if '=' not in raw_name:
            continue
        raw_name, raw_pcls = raw_name.split('=')
        if raw_name != name:
            continue
        try:
            pcls = clsmap[raw_pcls]
            return pcls(raw_formula)
        except Exception as e:
            raise CorruptedDataError(f'Failed to resolve \'{raw_pcls}\' formula for \'{raw_name}\'...\n{e}')
    if sentinel is SentinelValue:
        raise CorruptedDataError(f'Failed to find a formula for {name} in {raw_data}')
    return Formula(sentinel)


class Formula:
    name = 'base'
    def __init__(self, raw_param):
        self.__raw_param = raw_param

    @property
    def base_value(self):
        return self.__raw_param

    @property
    def repr(self):
        return f'[b]{self.__raw_param}[/b]'

    def value_repr(self, au=None, rounding=1, bold=True):
        if au and self.name != 'base':
            if bold:
                return f'[b]{round(self.get_value(*au), rounding)}[/b] ({self.repr})'
            else:
                return f'{round(self.get_value(*au), rounding)} ({self.repr})'
        return self.repr

    @property
    def raw_param(self):
        return self.__raw_param

    def get_value(self, api, uid):
        return self.__raw_param

    def full_str(self, key, nl=True):
        if not self.name == 'base':
            nl = '\n' if nl else ''
            return f'{nl}{key}{self.repr}'
        return ''

    def __repr__(self):
        return f'<{self.name} formula: {self.__raw_param}>'


class BonusFormula(Formula):
    name = 'bonus'
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
        return f'{self._base} + [b]{self._stat.name.lower()}[/b] ×{self._factor}'

    def get_value(self, api, uid):
        return self._base + self._factor * Mechanics.get_stats(api, uid, self._stat)


class ScaleFormula(Formula):
    name = 'scaling'
    ascending_scale = True

    def __init__(self, raw_param):
        super().__init__(raw_param)
        min_, stat, max_, curve = raw_param.split(', ')
        self._min = float(min_)
        if stat == 'time':
            self.get_stat = lambda a, u: ticks2s(a.tick)/60
            self.stat_name = 'time'
        else:
            self.get_stat = lambda a, u, s=str2stat(stat): Mechanics.get_stats(a, u, s)
            self.stat_name = stat
        self._max = float(max_)
        self._curve = float(curve)
        self._scale = self._max - self._min

    @property
    def base_value(self):
        return self._min if self.ascending_scale else self._max

    @property
    def repr(self):
        if self.ascending_scale:
            return f'{self._min} < [b]{self.stat_name}[/b]§{self._curve} < {self._max}'
        return f'{self._max} > [b]{self.stat_name}[/b]§{self._curve} > {self._min}'

    def get_value(self, api, uid):
        stat = self.get_stat(api, uid)
        scale = self._scale * Mechanics.scaling(stat, self._curve, ascending=self.ascending_scale)
        return self._min + scale


class ReducFormula(ScaleFormula):
    name = 'reduction'
    ascending_scale = False

    def __init__(self, raw_param):
        factor, stat, base, curve = raw_param.split(', ')
        raw_param = ', '.join([base, stat, factor, curve])
        super().__init__(raw_param)


class Effect:
    def __init__(self, phase, raw_data):
        pass

    def repr(self, au):
        return ''

    valid_mask_targets = {'self', 'single', 'area', 'selected'}
    valid_point_targets = {'self', 'source', 'point', 'single', 'selected'}
    valid_uid_targets = {'self', 'single', 'selected'}
    repr_mask_targets = {
        'self': 'self',
        'single': 'target unit',
        'area': 'area',
        'selected': 'linked unit',
    }
    repr_point_targets = {
        'self': 'self',
        'source': 'self',
        'point': 'target point',
        'single': 'target unit',
        'selected': 'linked unit',
    }
    repr_uid_targets = {
        'self': 'self',
        'single': 'target unit',
        'selected': 'linked unit',
    }

    @classmethod
    def resolve_target_mask(cls, api, uid, p, targets):
        if p == 'self':
            return Mechanics.mask(api, uid)
        if p == 'single':
            return targets.single
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
        if p == 'single':
            if targets.single.sum() == 0:
                raise RuntimeError(f'Failed to find uids for target {p} from targets {targets}')
            return api.get_position(np.flatnonzero(targets.single)[0])
        if p == 'selected':
            if targets.selected.sum() == 0:
                raise RuntimeError(f'Failed to find uids for target {p} from targets {targets}')
            return api.get_position(np.flatnonzero(targets.selected)[0])
        raise ValueError(f'Effect.resolve_target_point() expecting one of {self.valid_point_targets}, instead got: {p}')

    @classmethod
    def resolve_target_uid(cls, api, uid, p, targets):
        if p == 'self':
            return uid
        if p == 'single':
            return np.flatnonzero(targets.single)[0]
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
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'point'
        assert self.target in self.valid_point_targets

    def repr(self, au):
        if au:
            movespeed_str = f'{int(s2ticks(Mechanics.get_movespeed(*au)[0]))} movespeed'
        else:
            movespeed_str = 'movespeed'
        return f'[u][b]Walk[/b] at [b]{movespeed_str}[/b][/u]'

    def apply(self, api, uid, targets):
        target_point = self.resolve_target_point(api, uid, self.target, targets)
        Mechanics.apply_walk(api, Mechanics.mask(api, uid), target_point)


class EffectPush(Effect):
    effect_name = 'Push'
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        self.point = raw_data['point'] if 'point' in raw_data else 'point'
        assert self.point in self.valid_point_targets
        self.speed = resolve_formula('speed', raw_data, 0)
        self.duration = resolve_formula('duration', raw_data, 0)
        self.distance = resolve_formula('distance', raw_data, 0)

    def repr(self, au):
        if au:
            speed = self.speed.get_value(*au)
            distance = self.distance.get_value(*au)
            duration = self.duration.get_value(*au)
        else:
            speed = self.speed.base_value
            distance = self.distance.base_value
            duration = self.duration.base_value
        extra_str = ''
        subs = []
        if duration > 0:
            subs.append(f'[b]{round(duration, 1)} s[/b]')
        if distance > 0:
            subs.append(f'[b]{round(distance)} units[/b]')
        if subs:
            extra_str = ' and '.join(subs)
        if speed > 0:
            extra_str = f'{extra_str} at [b]{round(speed)}[/b] speed'
        if extra_str:
            extra_str = f' for {extra_str}'
        return f'[u][b]{self.effect_name}[/b]{extra_str}[/u][/b]{self.distance.full_str("Distance: ")}{self.duration.full_str("Duration: ")}{self.speed.full_str("Speed: ")}'

    def apply(self, api, uid, targets):
        # Resolve targets
        target_point = self.resolve_target_point(api, uid, self.point, targets)
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        target_mask = target_mask & Mechanics.moveable(api)
        if target_mask.sum() == 0:
            return
        # Resolve push/pull parameters
        distance = self.distance.get_value(api, uid)
        speed = ticks2s(self.speed.get_value(api, uid))
        duration = s2ticks(self.duration.get_value(api, uid))
        if speed + duration <= 0:
            return
        # Determine target points (consider distance limit)
        pos = api.get_positions(target_mask)
        vectors = (pos - target_point) if self.effect_name == 'Push' else (target_point - pos)
        target_points = np.full_like(pos, target_point, dtype=np.float64)
        if distance > 0:
            vsizes = np.atleast_1d(np.linalg.norm(vectors, axis=-1))
            vsizes[vsizes == 0] = 0.001
            vectors = vectors * (distance / vsizes)[:, None]
            target_points = pos + vectors
        # Determine speed/duration
        vsizes = np.linalg.norm(vectors, axis=-1)
        if speed == 0:
            speed = vsizes / duration
        elif duration == 0:
            speed = np.full((len(vectors)), speed, dtype=np.float64)
            duration = vsizes / speed
        # Apply
        api.set_move(target_mask, target_points, speed)
        api.set_status(target_mask, STATUS.BOUNDED, duration, 1)


class EffectPull(EffectPush):
    effect_name = 'Pull'


class EffectLoot(Effect):
    def __init__(self, phase, raw_data):
        self.range = resolve_formula('range', raw_data)

    def repr(self, au):
        if au:
            range = self.range.get_value(*au)
        else:
            range = self.range.base_value
        if range < 10**6:
            range_str = f' in [b]{int(range)} range[/b]'
        else:
            range_str = ''
        return f'[u][b]Loot[/b] {range_str}[/u]{self.range.full_str("Range: ")}'

    def apply(self, api, uid, targets):
        range = self.range.get_value(api, uid)
        Mechanics.apply_loot(api, uid, api.get_position(uid), range)


class EffectTeleport(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'point'
        self.offset = resolve_formula('offset', raw_data, 0)
        self.stop_move = 'keep_moving' not in raw_data.positional

    def repr(self, au):
        return f'[u][b]Teleport[/b][/u] to {self.repr_point_targets[self.target]}'

    def apply(self, api, uid, targets):
        target_point = self.resolve_target_point(api, uid, self.target, targets)
        offset = self.offset.get_value(api, uid)
        if offset > 0:
            current_pos = api.get_position(uid)
            target_vector = target_point - current_pos
            fixed_target_vector = normalize(target_vector, np.linalg.norm(target_vector)+offset)
            target_point = current_pos + fixed_target_vector
        reset_target = self.target == 'self'
        Mechanics.apply_teleport(api, uid, target_point, reset_target=self.stop_move)


class EffectTeleportHome(Effect):
    def repr(self, au):
        return '[u][b]Teleport home[/b][/u]'

    def apply(self, api, uid, targets):
        target = api.units[uid]._respawn_location
        Mechanics.apply_teleport(api, uid, target, reset_target=True)


class EffectStatus(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_mask_targets
        self.status = str2status(raw_data['status'])
        self.duration = resolve_formula('duration', raw_data, -1)
        self.duration_add = resolve_formula('duration_add', raw_data, 0)
        self.max_duration = resolve_formula('max_duration', raw_data, float('inf'))
        self.stacks = resolve_formula('stacks', raw_data, None)
        self.stacks_add = resolve_formula('stacks_add', raw_data, 0)
        self.max_stacks = resolve_formula('max_stacks', raw_data, float('inf'))

    def repr(self, au):
        if au:
            duration = self.duration.get_value(*au)
            duration_add = self.duration_add.get_value(*au)
            max_duration = self.max_duration.get_value(*au)
            stacks = self.stacks.get_value(*au)
            stacks_add = self.stacks_add.get_value(*au)
            max_stacks = self.max_stacks.get_value(*au)
        else:
            duration = self.duration.base_value
            duration_add = self.duration_add.base_value
            max_duration = self.max_duration.base_value
            stacks = self.stacks.base_value
            stacks_add = self.stacks_add.base_value
            max_stacks = self.max_stacks.base_value

        duration_str = ''
        dur_add_str = nsign_str(round(duration_add, 1)) if duration_add > 0 else ''
        dur_str_ = str(round(duration, 1)) if duration > 0 else ''
        if duration > 0 or duration_add > 0:
            duration_str = f' for [b]{dur_str_}{dur_add_str}s[/b]'

        stacks_str = []
        if stacks is not None:
            stacks_str.append(f'apply {round(stacks, 1)}' if stacks > 0 else 'Apply')
        if stacks_add > 0:
            stacks_str.append(f'add {round(stacks_add, 1)}' if stacks_add > 0 else 'Add')
        stacks_str = ' and '.join(stacks_str).capitalize()

        duration_total = (duration != 0) + duration_add
        stacks_total = (stacks is not None) + stacks_add
        if duration_total + stacks_total == 0:
            stacks_str = 'Remove all'
            duration_str = ''

        max_str = []
        if max_duration < float('inf'):
            max_str.append(f'[b]{round(max_duration, 1)}[/b]s')
        if max_stacks < float('inf'):
            max_str.append(f'[b]{round(max_stacks, 1)}[/b] stacks')
        max_str = ' up to ' + ' and '.join(max_str) if max_str else ''
        target_str = f' to {self.repr_mask_targets[self.target]}'
        subs = ''.join([
            self.duration.full_str("Duration: "),
            self.duration_add.full_str("Add duration: "),
            self.max_duration.full_str("Max duration: "),
            self.stacks.full_str("Stacks: "),
            self.stacks_add.full_str("Add stacks: "),
            self.max_stacks.full_str("Max stacks: "),
        ])
        return f'[u][b]{stacks_str} {self.status.name.lower()}[/b]{duration_str}{max_str}{target_str}[/u]{subs}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        if target_mask.sum() == 0:
            return
        duration = s2ticks(self.duration.get_value(api, uid))
        duration_add = s2ticks(self.duration_add.get_value(api, uid))
        max_duration = s2ticks(self.max_duration.get_value(api, uid))
        stacks = self.stacks.get_value(api, uid)
        stacks_add = self.stacks_add.get_value(api, uid)
        max_stacks = self.max_stacks.get_value(api, uid)

        if duration < 0:
            duration = targets.dt * 2 if targets.dt > 0 else None
        Mechanics.apply_debuff(api, target_mask, self.status,
            duration, stacks, duration_add, stacks_add,
            caster=uid)
        # Account for max
        duration_values = api.get_status(target_mask, self.status, value_name=STATUS_VALUE.DURATION)
        duration_values[duration_values > max_duration] = max_duration
        stack_values = api.get_status(target_mask, self.status, value_name=STATUS_VALUE.STACKS)
        stack_values[stack_values > max_stacks] = max_stacks
        api.set_status(target_mask, self.status, duration_values, stack_values)


class EffectStat(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_mask_targets
        self.stat, self.value = str2statvalue(raw_data['stat'])
        self.stat_name = self.stat.name.lower()
        self.delta = resolve_formula('delta', raw_data)

    def repr(self, au):
        delta = self.delta.get_value(*au) if au else self.delta.base_value
        stat_str = f'Gain {delta}' if delta >= 0 else f'Lose {delta}'
        return f'[u][b]{stat_str} {self.stat_name}[/b][/u]{self.delta.full_str("Delta: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        delta = self.delta.get_value(api, uid)
        api.set_stats(target_mask, self.stat, delta, value_name=self.value, additive=True)


class EffectSteal(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_mask_targets
        self.stat = str2stat(raw_data['stat'])
        self.stat_name = self.stat.name.lower()
        self.delta = resolve_formula('delta', raw_data)

    def repr(self, au):
        delta = self.delta.get_value(*au) if au else self.delta.base_value
        delta = round(delta, 3)
        stat_str = f'Steal {delta}' if delta >= 0 else f'Give {delta}'
        return f'[u][b]{stat_str} {self.stat_name}[/b][/u]{self.delta.full_str("Delta: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        if target_mask.sum() == 0:
            return
        delta = self.delta.get_value(api, uid)
        pre_sub = api.get_stats(target_mask, self.stat)
        api.set_stats(target_mask, self.stat, -delta, additive=True)
        post_sub = api.get_stats(target_mask, self.stat)
        stolen = pre_sub - post_sub
        if target_mask.sum() > 0:
            stolen = stolen.sum()
        api.set_stats(uid, self.stat, stolen, additive=True)


class EffectRegen(Effect):
    is_degen = False
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_mask_targets
        self.stat = str2stat(raw_data['stat'])
        self.stat_name = self.stat.name.lower()
        self.delta = resolve_formula('delta', raw_data)
        self.duration = resolve_formula('duration', raw_data, -1)
        self.decay = resolve_formula('decay', raw_data, 1)

    def repr(self, au):
        if au:
            delta = self.delta.get_value(*au)
            duration = self.duration.get_value(*au)
        else:
            delta = self.delta.base_value
            duration = self.duration.base_value
        regen_str = f'Regen {round(delta, 3)}' if not self.is_degen else f'Degen {round(delta, 3)}'
        duration_str = f' for [b]{round(duration, 1)}s[/b]' if duration > 0 else ''
        return f'[u][b]{regen_str} {self.stat_name}[/b]{duration_str}[/u]{self.delta.full_str("Delta /s: ")}{self.duration.full_str("Duration: ")}'

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        if target_mask.sum() == 0:
            return
        delta = ticks2s(self.delta.get_value(api, uid))
        if self.is_degen:
            delta *= -1
        duration = s2ticks(self.duration.get_value(api, uid))
        if duration < 0:
            duration = targets.dt
            decay = s2ticks(self.decay.get_value(api, uid))
            decay_multi = decay / duration
            delta /= decay_multi
            duration *= decay_multi
        Mechanics.apply_regen(api, target_mask, self.stat, duration, delta)


class EffectDegen(EffectRegen):
    is_degen = True


class EffectHit(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_mask_targets
        self.damage = resolve_formula('damage', raw_data)

    def repr(self, au):
        damage = self.damage.get_value(*au) if au else self.damage.base_value
        return f'[u][b]Hit[/b] for [b]{round(damage, 1)} normal[/b] damage[/u]{self.damage.full_str("Damage: ")}'

    def apply(self, api, uid, targets):
        damage = self.damage.get_value(api, uid)
        mask = self.resolve_target_mask(api, uid, self.target, targets)
        Mechanics.do_normal_damage(api, uid, mask, damage)


class EffectBlast(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'area'
        assert self.target in self.valid_mask_targets
        self.damage = resolve_formula('damage', raw_data)

    def repr(self, au):
        damage = self.damage.get_value(*au) if au else self.damage.base_value
        return f'[u][b]Blast[/b] for [b]{round(damage, 1)} blast[/b] damage[/u]{self.damage.full_str("Damage: ")}'

    def apply(self, api, uid, targets):
        damage = self.damage.get_value(api, uid)
        mask = self.resolve_target_mask(api, uid, self.target, targets)
        Mechanics.do_blast_damage(api, uid, mask, damage)


class EffectSelect(Effect):
    def __init__(self, phase, raw_data):
        self.ability = phase.ability
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_mask_targets

    def repr(self, au):
        return 'Select a target'

    undismissable_fails = {
        FAIL_RESULT.MISSING_TARGET,
        FAIL_RESULT.OUT_OF_RANGE,
        FAIL_RESULT.OUT_OF_BOUNDS,
    }
    def apply(self, api, uid, targets):
        if targets.fails & self.undismissable_fails:
            return
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        api.units[uid].cache[self.ability.cached_selected_key] = target_mask


class EffectUnselect(EffectSelect):
    def repr(self, au):
        return 'Unselect a target'

    def apply(self, api, uid, targets):
        api.units[uid].cache[self.ability.cached_selected_key] = None
        if uid not in api.logic.miss_feedback_uids:
            return
        Assets.play_sfx('ui', 'inactive', volume='feedback')


class EffectShowSelect(EffectSelect):
    def __init__(self, phase, raw_data):
        self.ability = phase.ability
        self.is_feedback = 'not_feedback' not in raw_data.positional
        self.target = raw_data['target'] if 'target' in raw_data else 'single'
        assert self.target in self.valid_uid_targets
        self.show_range_target = self.target if self.target in self.valid_point_targets else 'point'
        self.play_sfx = 'no_sfx' not in raw_data.positional
        self.show_range = resolve_formula('show_range', raw_data, 100)

    def repr(self, au):
        return ''

    def apply(self, api, uid, targets):
        if self.is_feedback and uid not in api.logic.miss_feedback_uids:
            return
        no_target = targets.fails & self.undismissable_fails
        show_range = self.show_range.get_value(api, uid)
        if show_range is not None:
            p1 = targets.source
            p2 = targets.point if no_target else self.resolve_target_point(api, uid, self.show_range_target, targets)
            hb_radius = Mechanics.get_stats(api, uid, STAT.HITBOX)
            p2 = p1 + normalize(p2-p1, show_range+hb_radius)
            api.add_visual_effect(VFX.LINE, 10, {'color': self.ability.color, 'width': 2, 'p1': p1, 'p2': p2})
        if no_target:
            return
        target_uid = self.resolve_target_uid(api, uid, self.target, targets)
        play_sfx = self.play_sfx and (uid in api.logic.sfx_feedback_uids)
        api.logic.draw_unit_selection(target_uid, play_sfx=play_sfx)


class EffectRecast(Effect):
    def __init__(self, phase, raw_data):
        self.ability = phase.ability

    def repr(self, au):
        return f'Cast the passive phase'

    def apply(self, api, uid, targets):
        self.ability.passive(api, uid, 0)


class EffectShopkeeper(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'area'
        assert self.target in self.valid_mask_targets

    def repr(self, au):
        if au:
            shop_name = Item.stat2category(self._get_shop_stacks(*au)).name.lower().capitalize()
            return f'Apply {shop_name} status'
        return 'Apply shop status based on caster\'s shop stat'

    @staticmethod
    def _get_shop_stacks(api, uid):
        return api.get_stats(uid, STAT.SHOP)

    def apply(self, api, uid, targets):
        target_mask = self.resolve_target_mask(api, uid, self.target, targets)
        stacks = self._get_shop_stacks(api, uid)
        Mechanics.apply_debuff(api, target_mask, STATUS.SHOP, targets.dt * 2, stacks)


class EffectMapEditor(Effect):
    def __init__(self, phase, raw_data):
        self.target = raw_data['target'] if 'target' in raw_data else 'point'
        assert self.target in self.valid_point_targets
        self.positional = raw_data.positional

    def repr(self, au):
        return f'Map editor {self.positional}'

    def apply(self, api, uid, targets):
        target_point = self.resolve_target_point(api, uid, self.target, targets)
        if 'add' in self.positional:
            tile = api.get_status(uid, STATUS.MAP_EDITOR, STATUS_VALUE.STACKS)
            api.units[uid].api.map.add_droplet(tile, target_point)
        elif 'remove' in self.positional:
            api.logic.map.remove_droplet(target_point)
        elif 'pipette' in self.positional:
            biome = api.units[uid].api.map.find_biome(target_point)
            api.set_status(uid, STATUS.MAP_EDITOR, 0, biome)
        elif 'toggle' in self.positional:
            tile = api.get_status(uid, STATUS.MAP_EDITOR, STATUS_VALUE.STACKS)
            api.logic.map.toggle_droplet(target_point)


class EffectSFX(Effect):
    def __init__(self, phase, raw_data):
        self.category = raw_data['category'] if 'category' in raw_data else 'ability'
        self.sfx = raw_data['sfx'] if 'sfx' in raw_data else phase.ability.sfx
        self.volume =  resolve_formula('volume', raw_data, 1)
        self.__volume = Settings.get_volume('sfx')

    def apply(self, api, uid, targets):
        Assets.play_sfx(self.category, self.sfx, volume=self.__volume * self.volume.get_value(api, uid))


class EffectVFXFlash(Effect):
    def __init__(self, phase, raw_data):
        self.duration = resolve_formula('duration', raw_data, 0.3)
        self.fade = resolve_formula('fade', raw_data, -1)
        color = str2color(raw_data['color']) if 'color' in raw_data else phase.ability.color
        self.color = self.color = modify_color(color, a=0.15)

    def apply(self, api, uid, targets):
        duration = s2ticks(self.duration.get_value(api, uid))
        fade = s2ticks(self.fade.get_value(api, uid))
        fade = {'fade': fade} if fade > 0 else {}
        api.add_visual_effect(VFX.BACKGROUND, duration, {'color': self.color, **fade})


class EffectVFXLine(Effect):
    def __init__(self, phase, raw_data):
        self.duration = resolve_formula('duration', raw_data, 0.15)
        self.fade = resolve_formula('fade', raw_data, -1)
        self.width = resolve_formula('width', raw_data, 2)
        self.color = str2color(raw_data['color']) if 'color' in raw_data else phase.ability.color
        self.p1 = raw_data['p1'] if 'p1' in raw_data else 'source'
        self.p2 = raw_data['p2'] if 'p2' in raw_data else ('point' if phase.targeting_point else 'single')
        assert self.p1 in self.valid_point_targets
        assert self.p2 in self.valid_point_targets
        self.length = resolve_formula('length', raw_data, None)
        self.scale = resolve_formula('scale', raw_data, 1)

    def apply(self, api, uid, targets):
        p1, p2 = (self.resolve_target_point(api, uid, p, targets) for p in (self.p1, self.p2))
        length = self.length.get_value(api, uid)
        scale = self.scale.get_value(api, uid)
        if scale != 1 or length is not None:
            size = np.linalg.norm(p2-p1) if length is None else length
            size *= scale
            p2 = p1 + normalize(p2-p1, size)
        duration = s2ticks(self.duration.get_value(api, uid))
        fade = s2ticks(self.fade.get_value(api, uid))
        fade = {'fade': fade} if fade > 0 else {}
        api.add_visual_effect(VFX.LINE, duration, {
            'color': self.color,
            'width': self.width.get_value(api, uid),
            'p1': p1, 'p2': p2,
            **fade,
        })


class EffectVFXCircle(Effect):
    def __init__(self, phase, raw_data):
        self.duration = resolve_formula('duration', raw_data, 0.1)
        self.radius = resolve_formula('radius', raw_data)
        self.fade = resolve_formula('fade', raw_data, -1)
        self.color = str2color(raw_data['color']) if 'color' in raw_data else phase.ability.color
        self.center = raw_data['center']
        assert self.center in self.valid_point_targets
        self.center_key = 'uid' if self.center in self.valid_uid_targets else 'center'
        self.resolve_method = self.resolve_target_uid if self.center_key == 'uid' else self.resolve_target_point
        self.include_hitbox = 'include_hitbox' in raw_data.positional

    def apply(self, api, uid, targets):
        radius = self.radius.get_value(api, uid)
        if self.include_hitbox:
            radius += Mechanics.get_stats(api, uid, STAT.HITBOX)
        fade = s2ticks(self.fade.get_value(api, uid))
        fade = {'fade': fade} if fade > 0 else {}
        params = {
            self.center_key: self.resolve_method(api, uid, self.center, targets),
            'radius': radius,
            'color': self.color,
            **fade,
        }
        duration = s2ticks(self.duration.get_value(api, uid))
        api.add_visual_effect(VFX.CIRCLE, duration, params)


class EffectVFXRect(Effect):
    def __init__(self, phase, raw_data):
        self.duration = resolve_formula('duration', raw_data, 0.1)
        self.fade = resolve_formula('fade', raw_data, -1)
        self.color = str2color(raw_data['color']) if 'color' in raw_data else phase.ability.color
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
        offset = Mechanics.get_stats(api, uid, STAT.HITBOX) if self.include_hitbox else 0
        rect = Rect.from_point(origin, target, width, length, offset)
        fade = s2ticks(self.fade.get_value(api, uid))
        fade = {'fade': fade} if fade > 0 else {}
        points = rect.points
        duration = s2ticks(self.duration.get_value(api, uid))
        api.add_visual_effect(VFX.QUAD, duration, {
            'points': points,
            'color': self.color,
            **fade,
        })


class EffectVFXSprite(Effect):
    def __init__(self, phase, raw_data):
        self.phase = phase
        self.duration = resolve_formula('duration', raw_data, 0.1)
        self.fade = resolve_formula('fade', raw_data, -1)
        self.category = raw_data['category'] if 'category' in raw_data else 'ability'
        self.sprite = raw_data['sprite'] if 'sprite' in raw_data else None
        self.fade = resolve_formula('fade', raw_data, -1)
        self.sizex = resolve_formula('size', raw_data)
        self.sizey = resolve_formula('size_y', raw_data, None)
        self.color = str2color(raw_data['color']) if 'color' in raw_data else phase.ability.color
        self.center = raw_data['center']
        assert self.center in self.valid_point_targets
        if self.center in self.valid_uid_targets and 'follow_unit' in raw_data.positional:
            self.center_key = 'uid'
        elif self.center in self.valid_point_targets:
            self.center_key = 'point'
        else:
            raise CorruptedDataError(f'vfx-sprite \"center\" not a valid point or single target')
        self.resolve_method = self.resolve_target_uid if self.center_key == 'uid' else self.resolve_target_point

    def apply(self, api, uid, targets):
        if self.sprite is None:
            source = self.phase.ability.sprite
        elif self.sprite == '*target' and self.center_key == 'uid':
            target_uid = self.resolve_method(api, uid, self.center, targets)
            source = api.units[target_uid].sprite
        elif self.sprite == '*me':
            source = api.units[uid].sprite
        else:
            source = Assets.get_sprite(self.category, self.sprite)
        sizex = self.sizex.get_value(api, uid)
        sizey = self.sizey.get_value(api, uid)
        if sizey is None:
            sizey = sizex
        fade = s2ticks(self.fade.get_value(api, uid))
        fade = {'fade': fade} if fade > 0 else {}
        duration = s2ticks(self.duration.get_value(api, uid))
        api.add_visual_effect(VFX.SPRITE, duration, {
            'source': source,
            self.center_key: self.resolve_method(api, uid, self.center, targets),
            'size': (sizex, sizey),
            'color': self.color,
            **fade,
        })


EFFECT_CLASSES = {
    'recast': EffectRecast,
    'vfx-flash': EffectVFXFlash,
    'vfx-line': EffectVFXLine,
    'vfx-circle': EffectVFXCircle,
    'vfx-rect': EffectVFXRect,
    'vfx-sprite': EffectVFXSprite,
    'sfx': EffectSFX,
    'mapeditor': EffectMapEditor,
    'shopkeeper': EffectShopkeeper,
    'select': EffectSelect,
    'unselect': EffectUnselect,
    'show_select': EffectShowSelect,
    'move': EffectMove,
    'teleport': EffectTeleport,
    'teleport-home': EffectTeleportHome,
    'loot': EffectLoot,
    'status': EffectStatus,
    'hit': EffectHit,
    'blast': EffectBlast,
    'stat': EffectStat,
    'steal': EffectSteal,
    'regen': EffectRegen,
    'degen': EffectDegen,
    'push': EffectPush,
    'pull': EffectPull,
}
