
import math
import numpy as np
from nutil.time import ping, pong
from nutil.random import SEED
from nutil.vars import normalize
from logic.encounter.stats import UnitStats as Stats
from logic.encounter.stats import StatNames as STAT
from logic.encounter.stats import ValueNames as VALUES
from logic.encounter.stats import AutoIntEnum
from logic.encounter.stats import argmin

from enum import Enum, auto


class EncounterAPI:
    def __init__(self, encounter):
        self.e = encounter

    @property
    def tick(self):
        return self.e.tick

    @property
    def units(self):
        return self.e.units

    def get_stats_table(self):
        return self.e.stats.table

    def get_stat(self, *args, **kwargs):
        return self.e.stats.get_stat(*args, **kwargs)

    def get_unit_stats(self, uid):
        return self.e.stats.get_unit_values(uid)

    def get_position(self, *args, **kwargs):
        return self.e.stats.get_position(*args, **kwargs)

    def debug_stats_table(self):
        return str(self.e.stats.table)

    def elapsed_time_ms(self):
        return self.e.ticktime * self.e.tick

    def update(self):
        self.e.update()

    def use_ability(self, *args, **kwargs):
        self.e.use_ability(*args, **kwargs)

    def pretty_stats(self, uid):
        s = ''
        stats = self.get_unit_stats(0)
        for stat in STAT:
            s += f'{stat.name}: {round(stats[stat.value], 2)}\n'
        return s

    def debug(self, *args, **kwargs):
        self.e.debug_action(*args, **kwargs)


class Encounter:
    TPS = 60
    MONSTER_COUNT = 5

    def __init__(self):
        self.abilities = {
            ABILITIES.MOVE: self.do_ability_move,
            ABILITIES.STOP: self.do_ability_stop,
            ABILITIES.ATTACK: self.do_ability_attack,
            ABILITIES.BLAST: self.do_ability_blast,
            ABILITIES.NUKE: self.do_ability_nuke,
            ABILITIES.TELEPORT: self.do_ability_teleport,
        }
        self.auto_tick = True
        self.ticktime = 1000 / self.TPS
        self.agency_resolution = 100
        self.__t0 = self.__last_tick = self.__last_agency = ping()
        self.stats = Stats()
        self.units = []
        self._create_player()
        self._create_monsters()
        self.api = EncounterAPI(self)

    @property
    def tick(self):
        return self.stats.tick

    def update(self):
        ticks = self._do_ticks()
        self._do_agency()

    def _do_ticks(self):
        if not self.auto_tick:
            return 0
        dt = pong(self.__last_tick)
        if dt < self.ticktime:
            return 0
        ticks = int(dt // self.ticktime)
        if ticks == 0:
            return 0
        self.__last_tick = ping()
        self.stats.do_tick(ticks)
        dt -= ticks * self.ticktime
        self.__last_tick -= dt
        return ticks

    def _do_agency(self):
        dt = pong(self.__last_agency)
        if dt < self.agency_resolution:
            return
        self.__last_agency = ping()
        for uid, unit in enumerate(self.units):
            if self.stats.get_stat(uid, STAT.HP) <= 0:
                # TODO kill unit (move somewhere harmless and zero stat deltas)
                self.stats.zero_deltas_targets(uid)
                continue
            abilities = unit.poll_abilities(self)
            if abilities is None:
                continue
            for ability, target in abilities:
                self.use_ability(uid, ability, target)

    def _create_unit(self, unit_type, location, allegience):
        stats = {
            **unit_type.STARTING_STATS,
            STAT.POS_X: location[0],
            STAT.POS_Y: location[1],
        }
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        unit = unit_type(api=self, uid=uid, allegience=allegience)
        self.units.append(unit)

    def _create_player(self):
        self._create_unit(Player, (500, 500), allegience=0)

    def _create_monsters(self):
        for i in range(self.MONSTER_COUNT):
            self._create_unit(
                unit_type=RoamingMonster,
                location=self.random_location(),
                allegience=1,
            )

    def use_ability(self, uid, ability, target):
        target = np.array(target)
        # print(f'Unit {self.units[uid].name} requested {self.abilities[ability].__name__} ({ability}) @ {target}')
        self.abilities[ability](uid, target)

    def do_ability_move(self, uid, target):
        move_speed = self.stats.get_stat(uid, STAT.MOVE_SPEED)
        current_pos = self.stats.get_position(uid)
        target_vector = target - current_pos
        delta = normalize(target_vector, move_speed)
        for i, n in ((0, STAT.POS_X), (1, STAT.POS_Y)):
            self.stats.set_stat(uid, n, {
                VALUES.DELTA: delta[i],
                VALUES.TARGET_VALUE: target[i],
            })

    def do_ability_teleport(self, uid, target):
        pos = self.stats.get_position(uid)
        range = self.stats.get_stat(uid, STAT.RANGE)
        if math.dist(pos, target) > range*2:
            return
        self.stats.set_stat(uid, [STAT.POS_X, STAT.POS_Y], {VALUES.VALUE: target, VALUES.TARGET_VALUE: target})

    def do_ability_stop(self, uid, target):
        current_pos = self.stats.get_position(uid)
        self.do_ability_move(uid, current_pos)

    def do_ability_attack(self, uid, target):
        pos = self.stats.get_position(uid)
        range = self.stats.get_stat(uid, STAT.RANGE)
        enemies = self.enemy_uids(uid)
        nearest_enemy, dist = self.nearest_uid(target, enemies)
        enemy_pos = self.stats.get_position(nearest_enemy)
        if math.dist(pos, enemy_pos) > range:
            return
        damage = self.stats.get_stat(uid, STAT.DAMAGE)
        self.stats.modify_stat(nearest_enemy, STAT.HP, -damage)
        print(f'Did {damage} damage to {self.units[nearest_enemy].name}')

    def do_ability_blast(self, uid, target):
        print('not implemented blast. todo: find targets in aoe.')

    def do_ability_nuke(self, uid, target):
        print('not implemented nuke. todo: find targets in aoe.')

    def enemy_uids(self, uid):
        unit = self.units[uid]
        enemy_mask = [_u.allegience != unit.allegience for _u in self.units]
        return enemy_mask

    def nearest_uid(self, point, mask=None):
        distances = self.stats.get_distances(point)
        uid = argmin(distances, mask)
        return uid, distances[uid]

    def debug_action(self, *args, **kwargs):
        print(f'Debug {args} {kwargs}')
        if 'auto_tick' in kwargs:
            v = kwargs['auto_tick']
            self.auto_tick = v if v is not None else not self.auto_tick
            print('set auto tick', self.auto_tick)
            self.__last_tick = ping()
        if 'tick' in kwargs:
            v = kwargs['tick']
            print('doing ticks', v)
            self.stats.do_tick(v)

    def random_location(self):
        return SEED.r*1000, SEED.r*1000


class Unit:
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
    STARTING_STATS = {
        STAT.MOVE_SPEED: 1,
        STAT.HP: 100,
        STAT.RANGE: 50,
        STAT.DAMAGE: 1,
    }

    def startup(self, api):
        self._name = 'Player'
        self.color_code = 0


class RoamingMonster(Unit):
    STARTING_STATS = {
        STAT.MOVE_SPEED: 0.8,
        STAT.HP: 40,
        STAT.RANGE: 45,
        STAT.DAMAGE: 1,
    }

    def startup(self, api):
        self._name = 'Roaming monster'
        self.color_code = 1
        self.last_move = ping() - (SEED.r * 5000)

    def poll_abilities(self, api):
        abilities = [(ABILITIES.ATTACK, api.stats.get_position(self.uid))]
        if pong(self.last_move) > 5000:
            self.last_move = ping()
            ability = ABILITIES.MOVE if SEED.r < 0.8 else ABILITIES.STOP
            target = api.random_location()
            abilities.append((ability, target))
        return abilities


class ABILITIES(AutoIntEnum):
    MOVE = auto()
    STOP = auto()
    ATTACK = auto()
    BLAST = auto()
    NUKE = auto()
    TELEPORT = auto()
