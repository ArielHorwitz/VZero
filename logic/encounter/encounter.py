
import math, copy
import numpy as np
from nutil.display import nprint
from nutil.time import ping, pong, RateCounter, pingpong
from nutil.random import Seed, SEED
from nutil.vars import normalize, NP
from logic.encounter.api import EncounterAPI
from logic.encounter.stats import UnitStats
from logic.units import Units
from logic.mechanics.common import *
from logic.mechanics.casting import Cast


RNG = np.random.default_rng()


class Encounter:
    DEFAULT_TPS = 120
    SPAWN_MULTIPLIER = 2
    MAP_SIZE = (5_000, 5_000)
    AGENCY_PHASE_COUNT = 10

    @classmethod
    def new_encounter(cls):
        return cls().api

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
        self.stats = UnitStats()
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
        # Player abilities
        if self.api.mask_alive()[0]:
            abilities = self.api.units[0].poll_abilities(self.api)
            if abilities is not None:
                for ability, target in abilities:
                    self.use_ability(ability, target, uid=0)
        # Monster abilities
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
        spawn_zone_radius = 500
        map_edge = np.array([200, 200])
        camps = RNG.random((10_000, 2))*(self.map_size-map_edge*2)+map_edge
        bl = self.api.map_center - spawn_zone_radius
        tr = self.api.map_center + spawn_zone_radius
        out_box_mask = np.invert(NP.in_box_mask(camps, bl, tr))
        return camps[out_box_mask]

    def _create_unit(self, unit_type, location, allegience):
        # Create stats
        stats = Units.get_starting_stats(unit_type)
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        # Set spawn location
        self.api.set_position(uid, location, value_name=(VALUE.CURRENT, VALUE.TARGET_VALUE))
        # Create agency
        unit = Units.new_unit(unit_type, api=self.api, uid=uid, allegience=allegience)
        self.units.append(unit)

    def _create_player(self):
        spawn = self.map_size/2
        # spawn = np.zeros(2)
        self._create_unit('player', spawn, allegience=0)

    def _create_monsters(self):
        i = -1
        cluster_index = -1
        for type_index, d in enumerate(Units.SPAWN_WEIGHTS.items()):
            unit_type, (spawn_weight, cluster_size) = d
            if spawn_weight == 0:
                cluster_count = 1
            else:
                cluster_count = max(1, round(spawn_weight * self.SPAWN_MULTIPLIER))
            for c in range(cluster_count):
                cluster_index += 1
                for u in range(cluster_size):
                    i += 1
                    self._create_unit(
                        unit_type=unit_type,
                        location=self.monster_camps[cluster_index],
                        allegience=1,
                    )
            print(f'Spawned {(c+1)*(u+1)} {unit_type}')

    # UTILITY
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
        d = self.stats.get_stats(0, STAT.HP)
        print(d)

    # ABILITIES
    def use_ability(self, ability, target, uid=0):
        if self.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
            print(f'Unit {uid} is dead and requested ability {ability}')
            return FAIL_RESULT.INACTIVE
        target = np.array(target)
        if (target > self.map_size).any() or (target < 0).any():
            return FAIL_RESULT.OUT_OF_BOUNDS

        r = Cast.cast_ability(ability, self.api, uid, target)

        if r is None:
            print(f'Ability method {callback_name} return result not implemented.')
            r = FAIL_RESULT.CRITICAL_ERROR
        return r
