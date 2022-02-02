import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import copy
import numpy as np
from nutil.display import nprint
from engine.common import *


DMOD_CACHE_SIZE = 10_000
COLLISION_PASSES = 1
COLLISION_DEFAULT = True


class UnitStats:
    # STAT VALUES
    def get_stats(self, index, stat, value_name=None):
        if value_name is None:
            value_name = VALUE.CURRENT
        return self.table[index, stat, value_name]

    def set_stats(self, index, stat, stat_value, value_name=None,
                  additive=False, multiplicative=False):
        if value_name is None:
            value_name = VALUE.CURRENT
        cv = self.table[index, stat, value_name]
        if additive:
            stat_value += cv
        elif multiplicative:
            stat_value *= cv
        self.table[index, stat, value_name] = stat_value

    def get_status(self, index, status, value_name=None):
        """
        Get a status duration/stacks. Passing neither to value_name will return
        the stacks only if duration > 0.
        """
        duration = self.status_table[index, status, STATUS_VALUE.DURATION]
        amp = self.status_table[index, status, STATUS_VALUE.STACKS]
        if value_name is STATUS_VALUE.DURATION:
            return duration
        elif value_name is STATUS_VALUE.STACKS:
            return amp
        elif value_name is None:
            return amp * (duration > 0)
        raise ValueError(f'get_status value_name {value_name} unrecognized')

    def set_status(self, index, status, duration, stacks):
        self.status_table[index, status, STATUS_VALUE.DURATION] = duration
        self.status_table[index, status, STATUS_VALUE.STACKS] = stacks

    def get_cooldown(self, index, ability=None):
        if ability is None:
            ability = slice(None)
        return self.cooldowns[index, ability]

    def set_cooldown(self, index, ability, value):
        self.cooldowns[index, ability] = value

    # SPECIAL VALUES
    def get_position(self, index=None, value_name=None):
        if index is None:
            index = slice(None)
        if value_name is None:
            value_name = VALUE.CURRENT
        if isinstance(index, np.ndarray):
            return np.column_stack(self.table[index, a, VALUE.CURRENT] for a in (STAT.POS_X, STAT.POS_Y))
        return self.table[index, (STAT.POS_X, STAT.POS_Y), value_name]

    def set_position(self, index, pos, value_name=None,
        reset_delta_target=False, halt=False,
    ):
        if value_name is None:
            value_name = VALUE.CURRENT
        self.table[index, (STAT.POS_X, STAT.POS_Y), value_name] = pos
        if halt is True:
            self.table[index, (STAT.POS_X, STAT.POS_Y), VALUE.TARGET] = pos
        if reset_delta_target is True:
            self._reset_delta_target(index)

    def _reset_delta_target(self, index, velocity=None):
        # Find vector
        pos = self.table[index, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT]
        target = self.table[index, (STAT.POS_X, STAT.POS_Y), VALUE.TARGET]
        vector = target - pos
        if velocity is None:
            velocity = np.linalg.norm(self.table[index, (STAT.POS_X, STAT.POS_Y), VALUE.DELTA], axis=-1)
        vsize = np.linalg.norm(vector, axis=-1)
        vscale = velocity
        vscale[vsize != 0] /= vsize[vsize != 0]
        vector *= vscale[:, np.newaxis]
        new_delta = vector
        self.table[index, (STAT.POS_X, STAT.POS_Y), VALUE.DELTA] = new_delta

    def get_velocity(self, index=None):
        if index is None:
            index = slice(None)
        v = self.get_position(index, value_name=VALUE.DELTA)
        return np.linalg.norm(v)

    def get_distances(self, point, index=None, include_hitbox=True):
        if isinstance(index, int) or isinstance(index, np.int):
            _ = np.zeros(len(self.table), dtype=np.bool)
            _[index] = True
            index = _
        elif index is None:
            index = np.ones(len(self.table), dtype=np.bool)
        positions = np.column_stack(self.table[index, a, VALUE.CURRENT] for a in (STAT.POS_X, STAT.POS_Y))
        dist = np.linalg.norm(positions - np.array(point), axis=-1)
        if include_hitbox is True:
            dist -= self.table[index, STAT.HITBOX, VALUE.CURRENT]
            if isinstance(dist, np.ndarray):
                dist[dist<0] = 0
            elif dist < 0:
                dist = 0
        return dist

    def unit_distance(self, index1, index2=None, include_hitbox=True):
        position = self.table[index1, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT]
        if index2 is None:
            index2 = slice(None)
        positions = self.table[index2, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT]
        dist = np.linalg.norm(position - positions, axis=-1)
        if include_hitbox is True:
            dist -= self.table[index1, STAT.HITBOX, VALUE.CURRENT]
            dist -= self.table[index2, STAT.HITBOX, VALUE.CURRENT]
            if isinstance(dist, np.ndarray):
                dist[dist<0] = 0
            elif dist < 0:
                dist = 0
        return dist

    def set_collision(self, index, colliding=True):
        self._collision_flags[index] = colliding

    # ADD/REMOVE UNIT STATS
    def add_unit(self, unit_stats=None):
        # Base stats entry
        logger.debug(f'Adding new unit stats: {unit_stats}')
        if unit_stats is None:
            unit_stats = np.zeros(self.table.shape[1:])
        unit_stats = unit_stats[np.newaxis, :, :]
        self.table = np.concatenate((self.table, unit_stats), axis=0)
        # Dmod entry
        new_column = np.zeros((DMOD_CACHE_SIZE, 1))
        self._dmod_targets = np.concatenate((self._dmod_targets, new_column), axis=1)
        # Status entry
        unit_status = np.zeros((1, self.status_count, self.status_values_count))
        unit_status[:, :, STATUS_VALUE.DURATION] = -1
        self.status_table = np.concatenate((self.status_table, unit_status), axis=0)
        # Cooldowns entry
        unit_cooldowns = np.zeros((1, self.ability_count))
        self.cooldowns = np.concatenate((self.cooldowns, unit_cooldowns), axis=0)
        # Live flag
        self._flags_alive = np.append(self._flags_alive, [False])
        self._collision_flags = np.append(self._collision_flags, [COLLISION_DEFAULT])
        assert len(self.table) == len(self.status_table) == len(self.cooldowns) == self._dmod_targets.shape[1] == len(self._flags_alive) == len(self._collision_flags)
        return len(self.table) - 1

    def add_dmod(self, ticks, units, stat, delta):
        logger.debug(f'Adding dmod. ticks: {ticks}, stat: {stat.name}, delta: {delta}, units: {units.nonzero()[0]}')
        i = self._dmod_index % DMOD_CACHE_SIZE
        self._dmod_effects_add[i, stat] = delta
        self._dmod_ticks[i] = ticks
        self._dmod_targets[i] = units
        self._dmod_index += 1
        return i

    def kill_stats(self, index):
        self.table[index, :, VALUE.DELTA] = 0
        self.table[index, :, VALUE.TARGET] = 0

    # TICK
    def do_tick(self, ticks):
        self.tick += ticks
        hp_zero = self._do_stat_deltas(ticks)
        for _ in range(COLLISION_PASSES):
            self._collision_push()
        status_zero = self._do_status_deltas(ticks)
        self._do_cooldown_deltas(ticks)
        return hp_zero, status_zero

    def _dmod_deltas(self):
        active_dmods = self._dmod_ticks > 0
        active_targets = self._dmod_targets[active_dmods]
        active_effects_add = self._dmod_effects_add[active_dmods]
        # Reshape targets and effects and compare
        active_targets = active_targets[:, :, np.newaxis]
        active_effects_add = active_effects_add[:, np.newaxis, :]
        dmod_add = active_targets * active_effects_add
        delta_add = np.sum(dmod_add, axis=0)
        return delta_add

    def _do_stat_deltas(self, ticks):
        current_values = self.table[:, :, VALUE.CURRENT]
        # Find deltas
        deltas = self.table[:, :, VALUE.DELTA] * ticks
        active_dmods = self._dmod_ticks > 0
        dmod_count = active_dmods.sum()
        if dmod_count > 0:
            delta_add = self._dmod_deltas() * ticks
            deltas = copy.copy(deltas) + delta_add
            self._dmod_ticks -= ticks
        live_units = self.table[:, STAT.HP, VALUE.CURRENT] > 0
        deltas *= live_units.reshape(len(self.table), 1)

        min_values = self.table[:, :, VALUE.MIN]
        max_values = self.table[:, :, VALUE.MAX]
        target_values = self.table[:, :, VALUE.TARGET]
        target_value_diffs = target_values - current_values

        # Find which values are changed by delta, and which reach their target
        tv_same_direction = np.equal(np.greater_equal(target_value_diffs, 0), np.greater_equal(deltas, 0))
        tv_smaller_than_delta = np.less_equal(np.abs(target_value_diffs), np.abs(deltas))
        reaching_target = np.logical_and(tv_same_direction, tv_smaller_than_delta)
        at_target = np.logical_or(reaching_target, np.equal(target_value_diffs, 0))
        not_at_target = np.invert(at_target)

        # Add deltas or set at target
        current_values[not_at_target] += deltas[not_at_target]
        current_values[at_target] = target_values[at_target]

        # Cap at min and max value
        below_min_mask = current_values < min_values
        above_max_mask = current_values > max_values
        current_values[below_min_mask] = min_values[below_min_mask]
        current_values[above_max_mask] = max_values[above_max_mask]

        # Return a list of units that reached 0 HP
        hp_below_zero = self.table[:, STAT.HP, VALUE.CURRENT] <= 0
        hp_zero = self._flags_alive & hp_below_zero
        self._flags_alive = np.invert(hp_below_zero)
        return hp_zero.nonzero()[0]

    def _do_status_deltas(self, ticks):
        already_at_zero = self.status_table[:, :, STATUS_VALUE.DURATION] <= 0
        will_be_at_zero = self.status_table[:, :, STATUS_VALUE.DURATION] - ticks <= 0
        reaching_zero_now = np.invert(already_at_zero) & will_be_at_zero
        self.status_table[:, :, STATUS_VALUE.DURATION] -= ticks
        return np.column_stack(reaching_zero_now.nonzero())

    def _do_cooldown_deltas(self, ticks):
        self.cooldowns -= ticks

    def _collision_push(self):
        # Get full distance table
        hitboxes = self.table[:, STAT.HITBOX, VALUE.CURRENT]
        combined_hitboxes = hitboxes + hitboxes.reshape(len(self.table), 1)
        pos1 = self.table[:, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT]
        pos2 = pos1[:, np.newaxis, :]
        vectors = pos1 - pos2
        # Find collisions (both ways, when u0 pushed u1, u1 also pushes u0)
        distances = np.linalg.norm(vectors, axis=2)
        overlap = (distances - combined_hitboxes) * -1
        colliding = (overlap > 0) & (distances > 0)
        # Ignore units colliding with themselves
        colliding[np.identity(len(colliding), dtype=np.bool)] = False
        colliding[:, self._collision_flags == False] = False
        colliding[self._collision_flags == False, :] = False
        pushing, pushed = np.nonzero(colliding)
        if len(pushing) == 0:
            return

        # Find how heavy is the pushing unit
        push_weight = self.table[pushing, STAT.WEIGHT, VALUE.CURRENT]
        max_weight = self.table[pushing, STAT.WEIGHT, VALUE.MAX]
        push_weight[push_weight < 0] = max_weight[push_weight < 0]
        push_weight[push_weight == 0] = hitboxes[pushing][push_weight == 0]

        # Find how heavy is the pushed unit
        standing_weight = self.table[pushed, STAT.WEIGHT, VALUE.CURRENT]
        max_weight = self.table[pushed, STAT.WEIGHT, VALUE.MAX]
        standing_weight[standing_weight < 0] = max_weight[standing_weight < 0]
        standing_weight[standing_weight == 0] = hitboxes[pushed][standing_weight == 0]

        # Push only enough to eliminate hitbox overlap
        # Also consider the relative weight, as we calculate eacg side pushing the other
        final_push_weight = push_weight / (push_weight + standing_weight)
        push_distance = final_push_weight * overlap[pushing, pushed]
        push_vectors = vectors[pushing, pushed] / distances[pushing, pushed, np.newaxis]
        final_push_vectors = push_vectors * push_distance.reshape(len(push_distance), 1)

        # Update positions
        positions = self.get_position(pushed.reshape(len(pushed), 1))
        new_positions = positions + final_push_vectors
        self.set_position(
            pushed.reshape(len(pushed), 1), new_positions,
            reset_delta_target=True)

    # INTERNAL
    def __init__(self):
        self.tick = 0
        # Base stats table, containing all stats and all values.
        # See STAT class and VALUE class.
        self.stat_count = len(STAT)
        self.values_count = len(VALUE)
        self.table = np.zeros(
            shape=(0, self.stat_count, self.values_count),
            dtype=np.float64)
        # Status table, containing all status durations and stacks.
        self.status_count = len(STATUS)
        self.status_values_count = len(STATUS_VALUE)
        self.status_table = np.zeros(
            shape=(0, self.status_count, self.status_values_count),
            dtype=np.float64)
        # Cooldown table contains a cooldown value (-1 per tick)
        # For each ability
        self.ability_count = len(ABILITY)
        self.cooldowns = np.zeros(shape=(0, self.ability_count))
        # Delta modifier table contains temporary effects that can
        # add to each stat delta (without changing their source),
        # for a certain number of ticks.
        self._dmod_index = 0
        self._dmod_effects_add = np.zeros(
            shape=(DMOD_CACHE_SIZE, self.stat_count), dtype=np.float64)
        self._dmod_ticks = np.zeros(DMOD_CACHE_SIZE)
        self._dmod_targets = np.zeros(shape=(DMOD_CACHE_SIZE, 0))
        self._flags_alive = np.array([], dtype=np.bool)
        self._collision_flags = np.array([], dtype=np.bool)

    def print_table(self):
        with np.printoptions(precision=2, linewidth=10_000, threshold=10_000):
            nprint(self.table, 'Stat table')
            print(self.table.shape)

    def _dmod_repr(self, i):
        return f'Dmod: {i}, Ticks: {self._dmod_ticks[i]}, ' \
                f'Delta: {self._dmod_effects_add[i]}, ' \
                f'Targets: {self._dmod_targets[i].nonzero()[0]}'


def _make_unit_stats(data_dict):
    unit_matrix = np.zeros((1, len(STAT), len(VALUE)))
    for stat in STAT:
        if stat not in data_dict:
            raise ValueError(f'Missing starting stat: {stat.name}')
        values = data_dict[stat]
        for value in VALUE:
            if value not in values:
                raise ValueError(f'Missing starting stat value: {stat.name} {value.name}')
            unit_matrix[0, stat, value] = values[value]
    return unit_matrix


def get_unit_stats_template():
    return np.zeros(shape=(len(STAT), len(VALUE)))
