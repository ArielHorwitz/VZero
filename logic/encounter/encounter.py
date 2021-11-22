import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import numpy as np
from collections import defaultdict
from nutil.time import ping, pong, RateCounter, pingpong, ratecounter
from nutil.random import Seed, SEED
from logic.encounter.api import EncounterAPI
from logic.encounter.stats import UnitStats
from logic.mechanics.common import *
from logic.mechanics.player import Player
from logic.mechanics.mechanics import Mechanics


class Encounter:
    DEFAULT_TPS = 120
    AGENCY_PHASE_COUNT = 10
    AGENCY_PHASE_INTERVAL = 60

    @classmethod
    def new_encounter(cls, **kwargs):
        return cls(**kwargs).api

    def __init__(self, player_abilities=None):
        # Variable initialization
        self.eid = SEED.r
        self.dev_mode = False
        self.timers = defaultdict(RateCounter)
        self.timers['agency'] = defaultdict(RateCounter)
        self.__seed = Seed()
        self.auto_tick = True
        self.__tps = self.DEFAULT_TPS
        self.ticktime = 1000 / self.__tps
        self.agency_resolution = self.AGENCY_PHASE_INTERVAL / self.AGENCY_PHASE_COUNT
        self.__agency_phase = 0
        self.__last_agency_tick = 0
        self.__t0 = self.__last_tick = ping()
        self.stats = UnitStats()
        self.units = []
        self._visual_effects = []
        self.api = EncounterAPI(self)

        # Call mod to define map
        self.mod_api = Mechanics.mod_encounter_api_cls(self.api)

        # Create player
        if player_abilities is None or len(player_abilities) == 0:
            player_abilities = set(Mechanics.abilities_names)
        self._create_player(player_abilities)

        # Call mod to populate map
        self.mod_api.spawn_map()

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
        if not self.auto_tick:
            return
        next_agency = self.__last_agency_tick + self.agency_resolution
        # Player abilities
        if self.api.mask_alive()[0]:
            self.units[0].do_passive(self.api)
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
        # TODO make this more efficient - numpy can create the list of uids to iterate
        for uid in range(self.__agency_phase, len(self.units), self.AGENCY_PHASE_COUNT):
            with ratecounter(self.timers['agency'][uid]):
                unit = self.units[uid]
                if self.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
                    self.stats.kill_stats(uid)
                    continue
                unit.do_passive(self.api)
                abilities = unit.poll_abilities(self.api)
                if abilities is None:
                    continue
                for ability, target in abilities:
                    self.use_ability(ability, target, uid)

    # UNITS
    def _create_unit(self, unit_type, location, allegiance):
        logger.warning(f'"Encounter._create_unit()" is being phased out. Please use "Encounter.add_unit()"')
        # Create stats
        stats = Mechanics.get_starting_stats(unit_type)
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        # Set spawn location
        self.api.set_position(uid, location)
        self.api.set_position(uid, location, value_name=VALUE.TARGET_VALUE)
        # Create agency
        unit = Mechanics.get_new_unit(unit_type, api=self.api, uid=uid, allegiance=allegiance)
        self.units.append(unit)
        return uid

    def add_unit(self, unit_cls, name, stats, setup_params):
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        unit = unit_cls(self.api, uid, name, setup_params)
        self.units.append(unit)
        return unit

    def _create_player(self, player_abilities):
        stats = self.mod_api.player_stats
        player = self.add_unit(Player, 'Player', stats, setup_params=None)
        logger.info(f'Encounter initializing player abilities: {player_abilities}')
        player.set_abilities(player_abilities)
        player.allegiance = 0
        logger.info(f'Set player allegiance as {player.allegiance}')

    # UTILITY
    def add_visual_effect(self, *args, **kwargs):
        logger.debug(f'Adding visual effect with: {args} {kwargs}')
        self._visual_effects.append(VisualEffect(*args, **kwargs))

    def get_visual_effects(self):
        return self._visual_effects

    def debug_action(self, *args, **kwargs):
        logger.debug(f'Debug action: {args} {kwargs}')
        if 'dev_mode' in kwargs:
            self.dev_mode = not self.dev_mode
        if 'tick' in kwargs:
            self._do_ticks(kwargs['tick'])
        if 'tps' in kwargs:
            v = kwargs['tps']
            self.set_tps(v)
            logger.debug('set tps', self.__tps)

    # ABILITIES
    def use_ability(self, ability, target, uid=0):
        if not self.auto_tick and not self.dev_mode:
            return FAIL_RESULT.INACTIVE
        with ratecounter(self.timers['ability_single']):
            r = self._use_ability(ability, target, uid)
        return r

    def _use_ability(self, aid, target, uid):
        if self.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
            logger.warning(f'Unit {uid} is dead and requested ability {aid.name}')
            return FAIL_RESULT.INACTIVE

        target = np.array(target)
        if (target > self.mod_api.map_size).any() or (target < 0).any():
            return FAIL_RESULT.OUT_OF_BOUNDS

        return Mechanics.cast_ability(aid, self.api, uid, target)
