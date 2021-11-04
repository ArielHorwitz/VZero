
import math, copy
import numpy as np
from nutil.time import ping, pong, RateCounter, pingpong
from nutil.random import Seed, SEED
from nutil.vars import normalize, NP
from nutil.display import njoin
from logic.encounter.units import Player, get_starting_stats, SPAWN_WEIGHTS
from logic.encounter.stats import UnitStats as Stats
from logic.encounter.common import *


RNG = np.random.default_rng()


class EncounterAPI:
    @classmethod
    def new_encounter(cls):
        return Encounter().api

    def __init__(self, encounter):
        self.e = encounter

    def do_ticks(self, t=1):
        return self.e._do_ticks(t)

    def set_auto_tick(self, *a, **k):
        return self.e.set_auto_tick(*a, **k)

    def update(self):
        self.e.update()

    def use_ability(self, *args, **kwargs):
        return self.e.use_ability(*args, **kwargs)

    def get_visual_effects(self):
        return self.e.get_visual_effects()

    # STATS
    def get_stats(self, *args, **kwargs):
        return self.e.stats.get_stats(*args, **kwargs)

    def get_unit_stats(self, uid):
        return self.e.stats.get_unit_values(uid)

    def get_position(self, *args, **kwargs):
        return self.e.stats.get_position(*args, **kwargs)

    def debug_stats_table(self):
        return str(self.e.stats.table)

    # UTILITY
    def nearest_uid(self, *args, **kwargs):
        return self.e.nearest_uid(*args, **kwargs)

    def random_location(self, *a, **k):
        return self.e.random_location(*a, **k)

    # DEBUG
    def debug(self, *args, **kwargs):
        self.e.debug_action(*args, **kwargs)

    # PROPERTIES
    @property
    def map_size(self):
        return self.e.map_size

    @property
    def tick(self):
        return self.e.tick

    @property
    def units(self):
        return self.e.units

    @property
    def elapsed_time_ms(self):
        return self.e.ticktime * self.e.tick

    def pretty_stats(self, uid, stats=None):
        if stats is None:
            stats = STAT
        stat_table = self.e.stats.table
        s = [f'Allegience: {self.units[uid].allegience}']
        for stat in stats:
            current = stat_table[uid, stat, VALUE.CURRENT]
            delta = stat_table[uid, stat, VALUE.DELTA]
            d_str = f' + {delta:.2f}' if delta != 0 else ''
            max_value = stat_table[uid, stat, VALUE.MAX_VALUE]
            mv_str = f' / {max_value:.2f}' if max_value < 100_000 else ''
            s.append(f'{stat.name.lower().capitalize()}: {current:3.2f}{d_str}{mv_str}')
        return njoin(s)


class Encounter:
    DEFAULT_TPS = 120
    SPAWN_MULTIPLIER = 1
    MAP_SIZE = (3_000, 3_000)
    AGENCY_PHASE_COUNT = 10

    def __init__(self):
        self.__seed = Seed()
        self.map_size = np.array(Encounter.MAP_SIZE)
        self.auto_tick = False
        self.__tps = self.DEFAULT_TPS
        self.ticktime = 1000 / self.__tps
        self.agency_resolution = 60 / self.AGENCY_PHASE_COUNT
        self.__agency_phase = 0
        self.__last_agency_tick = 0
        self.__t0 = self.__last_tick = ping()
        self.stats = Stats()
        self.units = []
        self._visual_effects = []
        self.api = EncounterAPI(self)
        self.monster_camps = self._find_camps()
        self._create_player()
        self._create_monsters()
        self.tps = RateCounter()

    @property
    def tick(self):
        return self.stats.tick

    # TIME
    def set_auto_tick(self, auto=None):
        if auto is None:
            auto = not self.auto_tick
        self.auto_tick = auto
        self.__last_tick = ping()
        return self.auto_tick

    def set_tps(self, tps=None):
        if tps is None:
            tps = self.DEFAULT_TPS
        self.__tps = tps
        self.ticktime = 1000 / self.__tps

    def update(self):
        ticks = self._check_ticks()
        self._do_agency()

    def _check_ticks(self):
        dt = pong(self.__last_tick)
        if dt < self.ticktime or not self.auto_tick:
            return 0
        ticks = int(dt // self.ticktime)
        self.__last_tick = ping()
        dt -= ticks * self.ticktime
        self.__last_tick -= dt
        self._do_ticks(ticks)
        return ticks

    def _do_ticks(self, ticks):
        self.tps.ping()
        self.stats.do_tick(ticks)
        self._iterate_visual_effects(ticks)
        self.tps.pong()

    def _iterate_visual_effects(self, ticks):
        if len(self._visual_effects) == 0:
            return
        active_effects = []
        for effect in self._visual_effects:
            effect.tick(ticks)
            if effect.active:
                active_effects.append(effect)
        self._visual_effects = active_effects

    def _do_agency(self):
        next_agency = self.__last_agency_tick + self.agency_resolution
        if self.tick < next_agency:
            return
        self.__last_agency_tick = self.tick
        self.__agency_phase += 1
        self.__agency_phase %= self.AGENCY_PHASE_COUNT
        for uid in range(self.__agency_phase, len(self.units), self.AGENCY_PHASE_COUNT):
            unit = self.units[uid]
            # TODO kill unit (move somewhere harmless and zero stat deltas)
            if self.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
                self.stats.kill_stats(uid)
                continue
            abilities = unit.poll_abilities(self.api)
            if abilities is None:
                continue
            for ability, target in abilities:
                self.use_ability(ability, target, uid)

    # VFX
    def add_visual_effect(self, *args, **kwargs):
        self._visual_effects.append(VisualEffect(*args, **kwargs))

    def get_visual_effects(self):
        return self._visual_effects

    # UNITS
    def _find_camps(self):
        camps = RNG.random((10_000, 2))*self.map_size
        bl = self.map_center - 500
        tr = self.map_center + 500
        out_box_mask = np.invert(NP.in_box_mask(camps, bl, tr))
        return camps[out_box_mask]

    def _create_unit(self, unit_type, location, allegience):
        stats = get_starting_stats(custom={
            **unit_type.STARTING_STATS,
            STAT.POS_X: {
                VALUE.CURRENT: location[0],
                VALUE.TARGET_VALUE: location[0],
            },
            STAT.POS_Y: {
                VALUE.CURRENT: location[1],
                VALUE.TARGET_VALUE: location[1],
            },
        })
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        unit = unit_type(api=self.api, uid=uid, allegience=allegience)
        self.units.append(unit)

    def _create_player(self):
        spawn = self.map_size/2
        # spawn = np.zeros(2)
        self._create_unit(Player, spawn, allegience=0)

    def _create_monsters(self):
        i = -1
        cluster_index = -1
        for type_index, (monster_type, (spawn_weight, cluster_size)) in enumerate(SPAWN_WEIGHTS.items()):
            if spawn_weight == 0:
                cluster_count = 1
            else:
                cluster_count = max(1, round(spawn_weight * self.SPAWN_MULTIPLIER))
            for c in range(cluster_count):
                cluster_index += 1
                for u in range(cluster_size):
                    i += 1
                    self._create_unit(
                        unit_type=monster_type,
                        location=self.monster_camps[cluster_index],
                        allegience=1,
                    )
            print(f'Spawned {i} {monster_type.__name__}')

    # UTILITY
    def _do_damage(self, source_uid, target_uid, damage):
        source = self.units[source_uid]
        target = self.units[target_uid]
        stats = self.stats.get_stats()
        self.stats.modify_stat(target_uid, STAT.HP, -damage)
        if self.stats.get_stats(source_uid, STAT.BLOODLUST_LIFESTEAL, VALUE.CURRENT) > 0:
            self.stats.modify_stat(source_uid, STAT.HP, damage)
        if target_uid == 0:
            self.add_visual_effect(VisualEffect.BACKGROUND, 40)
            self.add_visual_effect(VisualEffect.SFX, 1, params={'sfx': 'ouch'})
        if target_uid == 0 or source_uid == 0:
            print(f'{self.units[source_uid].name} applied {damage:.2f} damage to {target.name}')

    def check_mana(self, uid, mana_cost):
        return self.stats.get_stats(uid, STAT.MANA, VALUE.CURRENT) < mana_cost

    def find_enemy_target(self, uid, target,
            include_hitbox=True,
            range=None,
        ):
        pos = self.stats.get_position(uid)
        if range is None:
            range = self.stats.get_stats(uid, STAT.RANGE, VALUE.CURRENT)
        enemies = self.mask_enemies(uid)
        target_uid, dist = self.nearest_uid(target, enemies)
        if target_uid is None:
            return None
        attack_pos = self.stats.get_position(target_uid)
        attack_target = self.units[target_uid]
        if include_hitbox:
            range += attack_target.HITBOX
        if math.dist(pos, attack_pos) > range:
            return None
        return target_uid

    def mask_alive(self):
        return self.stats.get_stats(None, STAT.HP, VALUE.CURRENT) > 0

    def mask_dead(self):
        return np.invert(self.mask_alive())

    def mask_enemies(self, uid):
        unit = self.units[uid]
        enemy_mask = [_u.allegience != unit.allegience for _u in self.units]
        return enemy_mask

    def nearest_uid(self, point, mask=None, alive=True):
        if mask is None:
            mask = np.ones(len(self.stats.table), dtype=np.int)
        if alive:
            alive = self.stats.table[:, STAT.HP, VALUE.CURRENT] > 0
            mask = np.logical_and(mask, alive)
        if mask.sum() == 0:
            return None, None
        distances = self.stats.get_distances(point)
        uid = argmin(distances, mask)
        return uid, distances[uid]

    def get_offset(self):
        return RNG.random(2) * 30

    def random_location(self):
        return np.array(tuple(SEED.r*_ for _ in self.map_size))

    @property
    def map_center(self):
        return self.map_size / 2

    def debug_action(self, *args, **kwargs):
        print(f'Debug {args} {kwargs}')
        if 'dmod' in kwargs:
            self.stats.add_dmod(5, self.mask_enemies(0), -3)
        if 'auto_tick' in kwargs:
            v = kwargs['auto_tick']
            self.set_auto_tick(v)
            print('set auto tick', self.auto_tick)
        if 'tick' in kwargs:
            v = kwargs['tick']
            print('doing ticks', v)
            self._do_ticks(v)
        if 'tps' in kwargs:
            v = kwargs['tps']
            self.set_tps(v)
            print('set tps', self.__tps)

    # ABILITIES
    def use_ability(self, ability, target, uid=0):
        if self.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
            print(f'Unit {uid} is dead and requested ability {ability}')
            return RESULT.INACTIVE
        target = np.array(target)
        if (target > self.map_size).any() or (target < 0).any():
            return RESULT.OUT_OF_BOUNDS
        callback_name = f'do_ability_{ability.name.lower()}'
        # print(f'Unit {self.units[uid].name} requested {callback_name} ({ability}) @ {target}')
        callback = getattr(self, callback_name)
        r = callback(uid, target)
        if r is None:
            print(f'Ability method {callback_name} return result not implemented.')
            r = RESULT.MISSING_RESULT
        return r

    def do_ability_move(self, uid, target):
        move_speed = self.stats.get_stats(uid, STAT.MOVE_SPEED, VALUE.CURRENT)
        current_pos = self.stats.get_position(uid)
        target_vector = target - current_pos
        delta = normalize(target_vector, move_speed)
        for i, n in ((0, STAT.POS_X), (1, STAT.POS_Y)):
            self.stats.set_stats(
                uid, n, (VALUE.DELTA, VALUE.TARGET_VALUE),
                values=(delta[i], target[i])
            )
        return ABILITIES.MOVE

    def do_ability_loot(self, uid, target):
        mana_cost = 0
        stats = self.stats.table
        if self.stats.get_stats(uid, STAT.MANA, VALUE.CURRENT) < mana_cost:
            return RESULT.MISSING_COST
        pos = self.stats.get_position(uid)
        range = self.stats.get_stats(uid, STAT.RANGE, VALUE.CURRENT)
        mask_gold = self.stats.get_stats(None, STAT.GOLD, VALUE.CURRENT) > 0
        lootables = np.logical_and(self.mask_dead(), mask_gold)
        loot_target, dist = self.nearest_uid(target, mask=lootables, alive=False)
        target_unit_hp = self.stats.get_stats(loot_target, STAT.HP, VALUE.CURRENT)
        loot_pos = self.stats.get_position(loot_target)
        if loot_target is None or target_unit_hp > 0:
            return RESULT.MISSING_TARGET
        target_unit = self.units[loot_target]
        if math.dist(pos, loot_pos) - target_unit.HITBOX > range:
            return RESULT.OUT_OF_RANGE
        looted_gold = stats[loot_target, STAT.GOLD, VALUE.CURRENT]
        stats[loot_target, STAT.GOLD, VALUE.CURRENT] = 0
        stats[loot_target, (STAT.POS_X, STAT.POS_Y), VALUE.CURRENT] = (-5000, -5000)
        stats[uid, STAT.GOLD, VALUE.CURRENT] += looted_gold
        stats[uid, STAT.MANA, VALUE.CURRENT] -= mana_cost
        print(f'Looted: {looted_gold} from {target_unit.name}')
        return ABILITIES.LOOT

    def do_ability_blink(self, uid, target):
        mana_cost = 50
        blink_range_factor = 50
        if self.stats.get_stats(uid, STAT.MANA, VALUE.CURRENT) < mana_cost:
            return RESULT.MISSING_COST
        pos = self.stats.get_position(uid)
        range = self.stats.get_stats(uid, STAT.RANGE, VALUE.CURRENT)
        if math.dist(pos, target) > range * blink_range_factor:
            return RESULT.OUT_OF_RANGE
        for axis, stat in enumerate((STAT.POS_X, STAT.POS_Y)):
            for value in (VALUE.CURRENT, VALUE.TARGET_VALUE):
                self.stats.set_stats(uid, stat, value, values=target[axis])
        self.stats.modify_stat(uid, STAT.MANA, -mana_cost)
        self.add_visual_effect(VisualEffect.LINE, 15, params={
            'p1': pos,
            'p2': target,
            'color_code': -1,
        })
        return ABILITIES.BLINK

    def do_ability_stop(self, uid, target):
        current_pos = self.stats.get_position(uid)
        self.do_ability_move(uid, current_pos)
        return ABILITIES.STOP

    def do_ability_attack(self, uid, target):
        mana_cost = 10
        stats = self.stats.table
        if self.check_mana(uid, mana_cost):
            return RESULT.MISSING_COST
        if stats[uid, STAT.ATTACK_DELAY, VALUE.CURRENT] > 0:
            return RESULT.ON_COOLDOWN
        target_uid = self.find_enemy_target(uid, target)
        if target_uid is None:
            return RESULT.MISSING_TARGET
        damage = self.stats.get_stats(uid, STAT.DAMAGE, VALUE.CURRENT)
        attack_delay_cost = stats[uid, STAT.ATTACK_DELAY_COST, VALUE.CURRENT]
        # apply
        stats[uid, STAT.ATTACK_DELAY, VALUE.CURRENT] += attack_delay_cost
        self.stats.modify_stat(uid, STAT.MANA, -mana_cost)
        self._do_damage(uid, target_uid, damage)
        self.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': self.stats.get_position(uid),
            'p2': self.stats.get_position(target_uid),
            'color_code': self.units[uid].color_code,
        })
        return ABILITIES.ATTACK

    def do_ability_bloodlust(self, uid, target):
        mana_cost = 25
        stats = self.stats.get_stats()
        if stats[uid, STAT.MANA, VALUE.CURRENT] < mana_cost:
            return RESULT.MISSING_COST
        if stats[uid, STAT.BLOODLUST_COOLDOWN, VALUE.CURRENT] > 0:
            return RESULT.ON_COOLDOWN
        units_mask = np.zeros(len(stats))
        units_mask[uid] = 1
        stats[uid, STAT.BLOODLUST_COOLDOWN, VALUE.CURRENT] = self.__tps*60
        stats[uid, STAT.BLOODLUST_LIFESTEAL, VALUE.CURRENT] = self.__tps*8
        self.add_visual_effect(VisualEffect.BACKGROUND, self.__tps*8)
        return ABILITIES.BLOODLUST

    def do_ability_beam(self, uid, target):
        self.stats.table[uid, STAT.HP, VALUE.MAX_VALUE] *= 0.9
        self.stats.table[uid, STAT.HP, VALUE.CURRENT] += 50
        return ABILITIES.BEAM

    def do_ability_vial(self, uid, target):
        stats = self.stats.get_stats()
        gold_cost = 40
        damage_buff = 10
        if stats[uid, STAT.GOLD, VALUE.CURRENT] < gold_cost:
            return RESULT.MISSING_COST
        stats[uid, STAT.GOLD, VALUE.CURRENT] -= gold_cost
        stats[uid, STAT.DAMAGE, VALUE.CURRENT] += damage_buff
        return ABILITIES.VIAL

    def do_ability_shard(self, uid, target):
        stats = self.stats.get_stats()
        gold_cost = 40
        attack_speed_buff = 0.1
        if stats[uid, STAT.GOLD, VALUE.CURRENT] < gold_cost:
            return RESULT.MISSING_COST
        stats[uid, STAT.GOLD, VALUE.CURRENT] -= gold_cost
        stats[uid, STAT.ATTACK_DELAY_COST, VALUE.CURRENT] *= (1-attack_speed_buff)
        return ABILITIES.SHARD

    def do_ability_moonstone(self, uid, target):
        stats = self.stats.get_stats()
        gold_cost = 40
        max_hp_buff = 10
        if stats[uid, STAT.GOLD, VALUE.CURRENT] < gold_cost:
            return RESULT.MISSING_COST
        stats[uid, STAT.GOLD, VALUE.CURRENT] -= gold_cost
        stats[uid, STAT.HP, VALUE.MAX_VALUE] += max_hp_buff
        return ABILITIES.MOONSTONE
