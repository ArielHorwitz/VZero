import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math, copy
import numpy as np
from collections import defaultdict
from nutil.time import ping, pong, RateCounter, pingpong, ratecounter
from nutil.random import Seed, SEED
from nutil.vars import normalize, NP
from logic.encounter.api import EncounterAPI
from logic.encounter.stats import UnitStats
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics

RNG = np.random.default_rng()


class Encounter:
    DEFAULT_TPS = 120
    SPAWN_MULTIPLIER = 3
    MAP_SIZE = (5_000, 5_000)
    AGENCY_PHASE_COUNT = 10

    @classmethod
    def new_encounter(cls, **kwargs):
        return cls(**kwargs).api

    def __init__(self, player_abilities=None):
        self.timers = defaultdict(RateCounter)
        self.timers['agency'] = defaultdict(RateCounter)
        self.__seed = Seed()
        self.map_size = np.array(Encounter.MAP_SIZE)
        self.auto_tick = True
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
        if player_abilities is None or len(player_abilities) == 0:
            player_abilities = set(Mechanics.abilities_names)
        self._create_player(player_abilities)
        self._create_monsters()

    @property
    def tick(self):
        return self.stats.tick

    @property
    def target_tps(self):
        return self.__tps

    # TIME
    def set_auto_tick(self, auto=None):
        if auto is None:
            auto = not self.auto_tick
        self.auto_tick = auto
        self.__last_tick = ping()
        logger.info(f'Set auto tick: {self.auto_tick}')
        return self.auto_tick

    def set_tps(self, tps=None):
        if tps is None:
            tps = self.DEFAULT_TPS
        self.__tps = tps
        self.ticktime = 1000 / self.__tps

    def update(self):
        with ratecounter(self.timers['logic_total']):
            with ratecounter(self.timers['tick_total']):
                ticks = self._check_ticks()
            with ratecounter(self.timers['agency_total']):
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
        with ratecounter(self.timers['tick_stats']):
            self.stats.do_tick(ticks)
        with ratecounter(self.timers['tick_vfx']):
            self._iterate_visual_effects(ticks)

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
            abilities = self.units[0].poll_abilities(self.api)
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
            with ratecounter(self.timers['agency'][uid]):
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
        logger.debug(f'Adding visual effect with: {args} {kwargs}')
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

    def _create_unit(self, unit_type, location, allegiance):
        # Create stats
        stats = Mechanics.get_starting_stats(unit_type)
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        # Set spawn location
        self.api.set_position(uid, location, value_name=(VALUE.CURRENT, VALUE.TARGET_VALUE))
        # Create agency
        unit = Mechanics.get_new_unit(unit_type, api=self.api, uid=uid, allegiance=allegiance)
        self.units.append(unit)

    def _create_player(self, player_abilities):
        logger.info(f'Player abilities: {player_abilities}')
        spawn = self.map_size/2
        self._create_unit('player', spawn, allegiance=0)
        self.units[0].set_abilities(player_abilities)

    def _create_monsters(self):
        i = -1
        cluster_index = -1
        for type_index, d in enumerate(Mechanics.spawn_weights.items()):
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
                        allegiance=1,
                    )
            logger.info(f'Spawned {(c+1)*(u+1)} {unit_type}')

    # UTILITY
    def debug_action(self, *args, **kwargs):
        logger.debug(f'Debug action: {args} {kwargs}')
        if 'dmod' in kwargs:
            self.stats.add_dmod(5, self.mask_enemies(0), -3)
        if 'tick' in kwargs:
            self._do_ticks(kwargs['tick'])
        if 'tps' in kwargs:
            v = kwargs['tps']
            self.set_tps(v)
            logger.debug('set tps', self.__tps)

    # ABILITIES
    def use_ability(self, ability, target, uid=0):
        if self.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
            logger.warning(f'Unit {uid} is dead and requested ability {ability.name}')
            return FAIL_RESULT.INACTIVE
        target = np.array(target)
        if (target > self.map_size).any() or (target < 0).any():
            return FAIL_RESULT.OUT_OF_BOUNDS

        r = Mechanics.cast_ability(ability, self.api, uid, target)

        if r is None:
            logger.warning(f'Ability method {callback_name} return result not implemented.')
            r = FAIL_RESULT.CRITICAL_ERROR
        return r
