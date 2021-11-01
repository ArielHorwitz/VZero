
import math, copy
import numpy as np
from nutil.time import ping, pong, pingpong, RateCounter
from nutil.random import SEED
from nutil.vars import normalize
from nutil.display import njoin
from logic.encounter.stats import UnitStats as Stats
from logic.encounter.stats import STAT, VALUE, argmin
from nutil.vars import AutoIntEnum
import enum


class EncounterAPI:
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
    TPS = 120
    MONSTER_COUNT = 50

    def __init__(self):
        self.map_size = np.array([3_000, 3_000])
        """
        self.abilities = {
            ABILITIES.MOVE: self.do_ability_move,
            ABILITIES.STOP: self.do_ability_stop,
            ABILITIES.LOOT: self.do_ability_loot,
            ABILITIES.ATTACK: self.do_ability_attack,
            ABILITIES.BLOOD_PACT: self.do_ability_blood_pact,
            ABILITIES.ADRENALINE: self.do_ability_adrenaline,
            ABILITIES.BLINK: self.do_ability_blink,
        }
        """
        self.auto_tick = False
        self.ticktime = 1000 / self.TPS
        self.agency_resolution = 500
        self.__t0 = self.__last_tick = self.__last_agency = ping()
        self.stats = Stats()
        self.units = []
        self._visual_effects = []
        self._create_player()
        self._create_monsters()
        self.tps = RateCounter()
        self.api = EncounterAPI(self)

    @property
    def tick(self):
        return self.stats.tick

    # TIME
    def update(self):
        ticks = self._check_ticks()
        self._do_agency()

    def _check_ticks(self):
        if not self.auto_tick:
            return 0
        dt = pong(self.__last_tick)
        if dt < self.ticktime:
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
        dt = pong(self.__last_agency)
        if dt < self.agency_resolution:
            return
        self.__last_agency = ping()
        for uid, unit in enumerate(self.units):
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
        unit = unit_type(api=self, uid=uid, allegience=allegience)
        self.units.append(unit)

    def _create_player(self):
        spawn = self.map_size/2
        # spawn = np.zeros(2)
        self._create_unit(Player, spawn, allegience=0)

    def _create_monsters(self):
        total_weights = sum(list(SPAWN_WEIGHTS.values()))
        weight_value = self.MONSTER_COUNT / total_weights
        for monster_type, spawn_weight in SPAWN_WEIGHTS.items():
            for i in range(round(spawn_weight*weight_value)):
                self._create_unit(
                    unit_type=monster_type,
                    location=self.random_location(),
                    allegience=1,
                )
            print(f'Spawned {i} {monster_type.__name__}')

    # UTILITY
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

    def random_location(self):
        return np.array(tuple(SEED.r*_ for _ in self.map_size))

    def set_auto_tick(self, auto=None):
        if auto is None:
            auto = not self.auto_tick
        self.auto_tick = auto
        return self.auto_tick

    def debug_action(self, *args, **kwargs):
        print(f'Debug {args} {kwargs}')
        if 'dmod' in kwargs:
            self.stats.add_dmod(5, self.mask_enemies(0), -3)
        if 'auto_tick' in kwargs:
            v = kwargs['auto_tick']
            self.set_auto_tick(v)
            print('set auto tick', self.auto_tick)
            self.__last_tick = ping()
        if 'tick' in kwargs:
            v = kwargs['tick']
            print('doing ticks', v)
            self._do_ticks(v)

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
        blink_range_factor = 3
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
        if self.stats.get_stats(uid, STAT.MANA, VALUE.CURRENT) < mana_cost:
            return RESULT.MISSING_COST
        if stats[uid, STAT.ATTACK_DELAY, VALUE.CURRENT] > 0:
            return RESULT.ON_COOLDOWN
        pos = self.stats.get_position(uid)
        range = self.stats.get_stats(uid, STAT.RANGE, VALUE.CURRENT)
        enemies = self.mask_enemies(uid)
        target_uid, dist = self.nearest_uid(target, enemies)
        if target_uid is None:
            return RESULT.MISSING_TARGET
        attack_target = self.units[target_uid]
        if target_uid is None:
            return RESULT.MISSING_TARGET
        enemy_pos = self.stats.get_position(target_uid)
        if math.dist(pos, enemy_pos) - attack_target.HITBOX > range:
            return RESULT.OUT_OF_RANGE
        damage = self.stats.get_stats(uid, STAT.DAMAGE, VALUE.CURRENT)
        attack_delay_cost = stats[uid, STAT.ATTACK_DELAY_COST, VALUE.CURRENT]
        # apply
        stats[uid, STAT.ATTACK_DELAY, VALUE.CURRENT] += attack_delay_cost
        self.stats.modify_stat(target_uid, STAT.HP, -damage)
        self.stats.modify_stat(uid, STAT.MANA, -mana_cost)
        self.add_visual_effect(VisualEffect.LINE, 5, {
            'p1': pos,
            'p2': enemy_pos,
            'color_code': self.units[uid].color_code,
        })
        if stats[uid, STAT.BLOODLUST_LIFESTEAL, VALUE.CURRENT] > 0:
            stats[uid, STAT.HP, VALUE.CURRENT] += damage
        if target_uid == 0:
            self.add_visual_effect(VisualEffect.BACKGROUND, 40)
            self.add_visual_effect(VisualEffect.SFX, 1, params={'sfx': 'ouch'})
        if target_uid == 0 or uid == 0:
            print(f'{self.units[uid].name} applied {damage:.2f} damage to {attack_target.name}')
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
        stats[uid, STAT.BLOODLUST_COOLDOWN, VALUE.CURRENT] = 60*60
        stats[uid, STAT.BLOODLUST_LIFESTEAL, VALUE.CURRENT] = 60*8
        self.add_visual_effect(VisualEffect.BACKGROUND, 120*8)
        return ABILITIES.BLOODLUST

    def do_ability_blood_pact(self, uid, target):
        self.stats.table[uid, STAT.HP, VALUE.MAX_VALUE] *= 0.9
        self.stats.table[uid, STAT.HP, VALUE.CURRENT] += 50
        return ABILITIES.BLOOD_PACT

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
        stats[uid, STAT.ATTACK_DELAY_COST, VALUE.DELTA] *= (1-attack_speed_buff)
        return ABILITIES.SHARD

    def do_ability_moonstone(self, uid, target):
        stats = self.stats.get_stats()
        gold_cost = 40
        hp_regen_buff = 0.015
        if stats[uid, STAT.GOLD, VALUE.CURRENT] < gold_cost:
            return RESULT.MISSING_COST
        stats[uid, STAT.GOLD, VALUE.CURRENT] -= gold_cost
        stats[uid, STAT.HP, VALUE.DELTA] += hp_regen_buff
        return ABILITIES.MOONSTONE


class VisualEffect:
    BACKGROUND = object()
    LINE = object()
    SFX = object()

    def __init__(self, eid, ticks, params=None):
        self.eid = eid
        self.total_ticks = ticks
        self.elapsed_ticks = 0
        self.params = {} if params is None else params

    def tick(self, ticks):
        self.elapsed_ticks += ticks

    @property
    def active(self):
        return self.elapsed_ticks <= self.total_ticks

    def __repr__(self):
        return f'<VisualEffect eid={self.eid} elapsed={self.elapsed_ticks} total={self.total_ticks}>'


class Unit:
    HITBOX = 20
    def __init__(self, api, uid, allegience, name=None):
        self.uid = uid
        self._name = 'Unnamed unit' if name is None else name
        self.allegience = allegience
        self.color_code = 1
        self.startup(api)

    @property
    def name(self):
        return f'{self._name} ({self.uid})'

    def startup(self, api):
        pass

    def poll_abilities(self, api):
        return None


class Player(Unit):
    SPRITE = 'robot-1.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 0},
        STAT.HP: {VALUE.CURRENT: 100, VALUE.MAX_VALUE: 100, VALUE.DELTA: 0.02},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 1},
        STAT.MANA: {VALUE.CURRENT: 100, VALUE.MAX_VALUE: 100, VALUE.DELTA: 0.2},
        STAT.RANGE: {VALUE.CURRENT: 100},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
        STAT.ATTACK_DELAY_COST: {VALUE.CURRENT: 100},
    }

    def startup(self, api):
        self._name = 'Player'
        self.color_code = 0


class BloodImp(Unit):
    SPRITE = 'flying-blood.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 5},
        STAT.HP: {VALUE.CURRENT: 40, VALUE.MAX_VALUE: 40, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.6},
        STAT.MANA: {VALUE.CURRENT: 10, VALUE.MAX_VALUE: 10, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 150},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
    }
    AGGRO_RANGE = 350

    def startup(self, api):
        self._name = 'Blood Imp'
        self.color_code = 1
        self.last_move = ping() - (SEED.r * 5000)

    def poll_abilities(self, api):
        my_pos = api.get_position(self.uid)
        abilities = [(ABILITIES.ATTACK, my_pos)]
        if pong(self.last_move) > 5000:
            self.last_move = ping()
            target = api.random_location()
            ability = ABILITIES.MOVE if SEED.r < 0.8 else ABILITIES.STOP
            player_pos = api.get_position(0)
            if math.dist(player_pos, my_pos) < self.AGGRO_RANGE:
                target = player_pos
            abilities.append((ability, target))
        return abilities


class FireElemental(BloodImp):
    SPRITE = 'fire-elemental.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 20},
        STAT.HP: {VALUE.CURRENT: 180, VALUE.MAX_VALUE: 180, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.7},
        STAT.MANA: {VALUE.CURRENT: 20, VALUE.MAX_VALUE: 20, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 70},
        STAT.DAMAGE: {VALUE.CURRENT: 60},
    }
    AGGRO_RANGE = 500

    def startup(self, api):
        self._name = 'Fire Elemental'
        self.color_code = 2
        self.last_move = ping() - (SEED.r * 5000)


class NullIce(Unit):
    SPRITE = 'null-tri.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 10},
        STAT.HP: {VALUE.CURRENT: 60, VALUE.MAX_VALUE: 60, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0},
        STAT.MANA: {VALUE.CURRENT: 20, VALUE.MAX_VALUE: 20, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 200},
        STAT.DAMAGE: {VALUE.CURRENT: 40},
    }

    def startup(self, api):
        self._name = 'Null Ice'
        self.color_code = 2

    def poll_abilities(self, api):
        return [(ABILITIES.ATTACK, api.get_position(self.uid))]


SPAWN_WEIGHTS = {
    NullIce: 5,
    BloodImp: 10,
    FireElemental: 3,
}


class ABILITIES(AutoIntEnum):
    # Basic
    MOVE = enum.auto()
    STOP = enum.auto()
    LOOT = enum.auto()
    # Spells
    ATTACK = enum.auto()
    BLOODLUST = enum.auto()
    BLOOD_PACT = enum.auto()
    BLINK = enum.auto()
    # Items
    VIAL = enum.auto()
    SHARD = enum.auto()
    MOONSTONE = enum.auto()


class RESULT(enum.Enum):
    NOMINAL = enum.auto()
    MISSING_RESULT = enum.auto()
    INACTIVE = enum.auto()
    OUT_OF_BOUNDS = enum.auto()
    MISSING_COST = enum.auto()
    OUT_OF_RANGE = enum.auto()
    ON_COOLDOWN = enum.auto()
    MISSING_TARGET = enum.auto()


DEFAULT_STARTING_STATS = {
    STAT.POS_X: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.POS_Y: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.GOLD: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.HP: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: 0,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MOVE_SPEED: {
        VALUE.CURRENT: 1,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MANA: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_00,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.RANGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.DAMAGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.ATTACK_DELAY: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: -1,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.ATTACK_DELAY_COST: {
        VALUE.CURRENT: 200,
        VALUE.MIN_VALUE: 10,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.BLOODLUST_LIFESTEAL: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: -1,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.BLOODLUST_COOLDOWN: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: -1,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
}


def get_starting_stats(base=None, custom=None):
    stats = copy.deepcopy(DEFAULT_STARTING_STATS if base is None else base)
    if custom is not None:
        for stat in STAT:
            if stat in custom:
                for value in VALUE:
                    if value in custom[stat]:
                        stats[stat][value] = custom[stat][value]
    return stats
