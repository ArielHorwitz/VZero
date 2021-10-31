
import numpy as np
import enum
from nutil.display import nprint


class UnitStats:
    def __init__(self):
        self.tick = 0
        print('Unit stats table using stat indices:')
        for stat_name in StatNames:
            print(stat_name.value, stat_name.name)
        self.stat_count = len(StatNames)
        self.values_count = len(ValueNames)
        self.table = np.ndarray(
            shape=(0, self.stat_count, self.values_count),
            dtype=np.float64
        )

    def do_tick(self, ticks):
        self.tick += ticks
        self._do_stat_deltas(ticks)

    def add_unit(self, starting_stats):
        print('Adding new unit stats:')
        unit_matrix = np.zeros((1, self.stat_count, self.values_count))
        for stat_name in StatNames:
            if stat_name not in starting_stats:
                raise ValueError(f'Missing starting stat: {stat_name.name}')
            v = starting_stats[stat_name]
            print(f'{stat_name.name:.<20} {v}')
            unit_matrix[0, stat_name.value, ValueNames.VALUE] = v
        self.table = np.concatenate((self.table, unit_matrix), axis=0)
        return len(self.table) - 1

    def set_value(self, index, stat_name, value, value_name=None):
        if value_name is None:
            value_name = ValueNames.VALUE
        self.table[index, stat_name, value_name] = value

    def get_position(self, index, value=None):
        if value is None:
            value = ValueNames.VALUE
        return self.table[index, (StatNames.POS_X, StatNames.POS_Y), value]

    def get_distances(self, point):
        positions = self.table[:, (StatNames.POS_X, StatNames.POS_Y), ValueNames.VALUE]
        vectors = positions - np.array(point)
        dist = np.linalg.norm(vectors, axis=1)
        return dist

    def get_stat(self, index, stat_name, value=None):
        if value is None:
            value = ValueNames.VALUE
        return self.table[index, stat_name, value]

    def set_stat(self, index, stat_name, values=None):
        if not isinstance(values, dict):
            values = {ValueNames.VALUE: values}
        for value_name, value in values.items():
            self.table[index, stat_name, value_name] = value

    def modify_stat(self, index, stat_name, value, multiplicative=False, values=None):
        if values is None:
            values = ValueNames.VALUE
        cv = self.table[index, stat_name, values]
        if multiplicative:
            value = cv * value
        else:
            value = cv + value
        self.table[index, stat_name, values] = value

    def get_unit(self, index):
        return self.table[index]

    def get_unit_values(self, index):
        return self.table[index, :, 0]

    def print_table(self):
        with np.printoptions(threshold=5):
            nprint(self.table, 'Stat table')
            print(self.table.shape)

    def _do_stat_deltas(self, ticks):
        DEBUG = False
        # TODO consider target ticks when enforcing deltas
        # TODO consider dead units when enforcing deltas

        current_values = self.table[:, :, ValueNames.VALUE]
        deltas = self.table[:, :, ValueNames.DELTA]
        target_values = self.table[:, :, ValueNames.TARGET_VALUE]
        target_ticks = self.table[:, :, ValueNames.TARGET_TICK]
        value_target_diffs = target_values - current_values

        # Find which values are changed by delta, and which reach their target
        tv_same_direction = np.equal(np.greater_equal(value_target_diffs, 0), np.greater_equal(deltas, 0))
        tv_smaller_than_delta = np.less_equal(np.abs(value_target_diffs), np.abs(deltas))
        at_target = np.logical_or(np.logical_and(tv_same_direction, tv_smaller_than_delta), np.equal(value_target_diffs, 0))
        not_at_target = np.invert(at_target)

        if DEBUG:
            print('-'*50)
            print('values', current_values)
            print('deltas', deltas)
            print('target values', target_values)
            print('target ticks', target_ticks)
            print('value target diffs', value_target_diffs)
            print('same direction', tv_same_direction)
            print('smaller than delta', tv_smaller_than_delta)
            print('reaching target', at_target)

        # Add deltas or set at target
        current_values[not_at_target] += deltas[not_at_target]
        current_values[at_target] = target_values[at_target]

        if DEBUG:
            self.print_table()

    def zero_deltas_targets(self, index):
        self.table[index, :, [ValueNames.DELTA, ValueNames.TARGET_VALUE, ValueNames.TARGET_TICK]] = 0


class AutoIntEnum(enum.IntEnum):
    def _generate_next_value_(name, start, count, last_values):
        return count


class StatNames(AutoIntEnum):
    POS_X = enum.auto()
    POS_Y = enum.auto()
    MOVE_SPEED = enum.auto()
    HP = enum.auto()
    RANGE = enum.auto()
    DAMAGE = enum.auto()


class ValueNames(AutoIntEnum):
    VALUE = enum.auto()
    DELTA = enum.auto()
    TARGET_VALUE = enum.auto()
    TARGET_TICK = enum.auto()


def argmin(a, mask=None):
    if mask is None:
        return np.array(a).argmin()
    out = np.flatnonzero(mask)[a[mask].argmin()]
    # Or
    # idx = np.flatnonzero(mask)
    # out = idx[a[idx].argmin()]
    return out
