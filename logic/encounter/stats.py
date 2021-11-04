
import copy
import numpy as np
import enum
from nutil.vars import AutoIntEnum
from nutil.display import nprint, njoin


DMOD_CACHE_SIZE = 10_000


class UnitStats:
    def __init__(self):
        self.tick = 0
        print('Unit stats table using stat indices:')
        for stat in STAT:
            print(stat.value, stat.name)
        print('Unit stats table using value indices:')
        for value in VALUE:
            print(value.value, value.name)
        self.stat_count = len(STAT)
        self.values_count = len(VALUE)
        self.table = np.ndarray(
            shape=(0, self.stat_count, self.values_count), dtype=np.float64)
        self._dmod_index = 0
        # Delta modifier table contains temporary effects that can
        # add to and multiply each stat delta (without changing their source),
        # for a certain number of ticks.
        self._dmod_effects_add = np.ndarray(shape=(DMOD_CACHE_SIZE, self.stat_count))
        self._dmod_ticks = np.zeros(DMOD_CACHE_SIZE)
        self._dmod_targets = np.zeros(shape=(DMOD_CACHE_SIZE, 0))

    def print_table(self):
        with np.printoptions(precision=2, linewidth=10_000, threshold=10_000):
            nprint(self.table, 'Stat table')
            print(self.table.shape)

    # ADD/REMOVE UNIT STATS
    def add_unit(self, starting_stats):
        unit_matrix = np.zeros((1, self.stat_count, self.values_count))
        for stat in STAT:
            if stat not in starting_stats:
                raise ValueError(f'Missing starting stat: {stat.name}')
            values = starting_stats[stat]
            for value in VALUE:
                if value not in values:
                    raise ValueError(f'Missing starting stat value: {stat.name} {value.name}')
                unit_matrix[0, stat, value] = values[value]
        self.table = np.concatenate((self.table, unit_matrix), axis=0)
        new_column = np.zeros((DMOD_CACHE_SIZE, 1))
        self._dmod_targets = np.concatenate((self._dmod_targets, new_column), axis=1)
        assert self._dmod_targets.shape[1] == len(self.table)
        return len(self.table) - 1

    def add_dmod(self, ticks, units, stat, delta):
        i = self._dmod_index
        # Empty effects for all stats (+0 additive, *1 multiplicative)
        self._dmod_effects_add[i, stat] = delta
        self._dmod_ticks[i] = ticks
        self._dmod_targets[i] = np.array(units)
        self._dmod_index += 1
        print(self._dmod_index)
        print(self._dmod_ticks)
        print(self._dmod_targets)
        print(units)
        print(self._dmod_effects_add)
        return i

    def kill_stats(self, index):
        self.table[index, :, [VALUE.DELTA, VALUE.TARGET_VALUE, VALUE.TARGET_TICK]] = 0

    # TICK
    def do_tick(self, ticks):
        self.tick += ticks
        self._do_stat_deltas(ticks)

    def _dmod_deltas(self):
        DEBUG = False

        active_targets = self._dmod_targets[active_dmods]
        active_effects_add = self._dmod_effects_add[active_dmods]
        # Reshape targets and effects and compare
        active_targets = active_targets[:, :, np.newaxis]
        active_effects_add = active_effects_add[:, np.newaxis, :]
        dmod_add = active_targets * active_effects_add
        delta_add = np.sum(dmod_add, axis=0)

        # debug
        if DEBUG:
            with np.printoptions(edgeitems=2, linewidth=10_000):
                print(self._dmod_index)
                nprint(self._dmod_ticks, 'dmod ticks / active')
                print(active_dmods)
                nprint(self._dmod_targets, 'dmod targets')
                nprint(self._dmod_effects_add, 'dmod effects (add)')
                nprint(delta_add, 'add deltas')

    def _do_stat_deltas(self, ticks):
        DEBUG = False
        # TODO consider target ticks when applying deltas
        # TODO consider dead units when applying deltas

        current_values = self.table[:, :, VALUE.CURRENT]
        # Raw deltas, without modifications
        deltas = self.table[:, :, VALUE.DELTA] * ticks
        # Find active modifications
        active_dmods = self._dmod_ticks > 0
        dmod_count = active_dmods.sum()
        if dmod_count > 0:
            print(f'Found {dmod_count} active dmods')
            delta_add = self._dmod_deltas() * ticks
            deltas = copy.deepcopy(deltas) + delta_add
            self._dmod_ticks -= ticks

        min_values = self.table[:, :, VALUE.MIN_VALUE]
        max_values = self.table[:, :, VALUE.MAX_VALUE]
        target_values = self.table[:, :, VALUE.TARGET_VALUE]
        target_ticks = self.table[:, :, VALUE.TARGET_TICK]
        target_value_diffs = target_values - current_values

        # Find which values are changed by delta, and which reach their target
        tv_same_direction = np.equal(np.greater_equal(target_value_diffs, 0), np.greater_equal(deltas, 0))
        tv_smaller_than_delta = np.less_equal(np.abs(target_value_diffs), np.abs(deltas))
        reaching_target = np.logical_and(tv_same_direction, tv_smaller_than_delta)
        at_target = np.logical_or(reaching_target, np.equal(target_value_diffs, 0))
        not_at_target = np.invert(at_target)

        if DEBUG:
            with np.printoptions(threshold=2, precision=2, edgeitems=2):
                print('-'*50)
                print('values', current_values)
                print('deltas', deltas)
                print('target values', target_values)
                print('target ticks', target_ticks)
                print('target value diffs', target_value_diffs)
                print('same direction', tv_same_direction)
                print('smaller than delta', tv_smaller_than_delta)
                print('reaching target', at_target)

        # Add deltas or set at target
        current_values[not_at_target] += deltas[not_at_target]
        current_values[at_target] = target_values[at_target]


        # Cap at min and max value
        below_min_mask = current_values < min_values
        above_max_mask = current_values > max_values
        if DEBUG:
            with np.printoptions(threshold=2, precision=2, edgeitems=2):
                self.print_table()
                print('-'*50)
                print('below min', below_min_mask)
                print('above max', above_max_mask)
                print('target values', target_values)
                print('target ticks', target_ticks)
        current_values[below_min_mask] = min_values[below_min_mask]
        current_values[above_max_mask] = max_values[above_max_mask]

        if DEBUG:
            with np.printoptions(threshold=2, precision=2, edgeitems=2):
                self.print_table()

    # STAT VALUES
    def _convert_indexing(self, index=None, stat=None, value=None, **kwargs):
        if index is None:
            index = slice(None)
        if stat is None:
            stat = slice(None)
        if value is None:
            value = slice(None)
        return index, stat, value

    def get_stats(self, *args, copy=False, **kwargs):
        index, stat, value = self._convert_indexing(*args, **kwargs)
        view = self.table[index, stat, value]
        if copy:
            return view.copy()
        return view

    def set_stats(self, *args, values=None, **kwargs):
        index, stat, value = self._convert_indexing(*args, **kwargs)
        try:
            self.table[index, stat, value] = values
        except ValueError as e:
            s = njoin([
                f'Indexing: {index, stat, value}',
                f'Old: {self.table[index, stat, value]}',
                f'New: {values}',
            ])
            raise ValueError(f'{s}\n{e}')

    def modify_stat(self, index, stat_name, value,
                    multiplicative=False, values=None):
        if values is None:
            values = VALUE.CURRENT
        cv = self.table[index, stat_name, values]
        if multiplicative:
            value = cv * value
        else:
            value = cv + value
        self.table[index, stat_name, values] = value

    # SPECIAL VALUES
    def get_position(self, index=None):
        if index is None:
            index = slice(None)
        return self.table[index, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT]

    def get_distances(self, point):
        positions = self.table[:, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT]
        vectors = positions - np.array(point)
        dist = np.linalg.norm(vectors, axis=1)
        return dist

    def get_unit_values(self, index):
        return self.table[index, :, 0]


class VALUE(AutoIntEnum):
    CURRENT = enum.auto()
    DELTA = enum.auto()
    TARGET_VALUE = enum.auto()
    TARGET_TICK = enum.auto()
    MIN_VALUE = enum.auto()
    MAX_VALUE = enum.auto()


class STAT(AutoIntEnum):
    POS_X = enum.auto()
    POS_Y = enum.auto()
    MOVE_SPEED = enum.auto()
    GOLD = enum.auto()
    HP = enum.auto()
    MANA = enum.auto()
    RANGE = enum.auto()
    DAMAGE = enum.auto()
    ATTACK_DELAY = enum.auto()
    ATTACK_DELAY_COST = enum.auto()
    BLOODLUST_LIFESTEAL = enum.auto()
    BLOODLUST_COOLDOWN = enum.auto()


def argmin(a, mask=None):
    if mask is None:
        return np.array(a).argmin()
    idx = np.flatnonzero(mask)
    out = idx[a[idx].argmin()]
    # Or
    # out = np.flatnonzero(mask)[a[mask].argmin()]
    return out
