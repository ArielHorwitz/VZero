import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
    AGENCY_PHASE_COUNT = 60

    @classmethod
    def new_encounter(cls, **kwargs):
        return cls(**kwargs).api

    def __init__(self, player_abilities=None):
        # Variable initialization
        self.eid = SEED.r
        self.dev_mode = False
        self.timers = defaultdict(RateCounter)
        self.timers['agency'] = defaultdict(lambda: RateCounter(sample_size=10))
        self.__seed = Seed()
        self.auto_tick = True
        self.__tps = self.DEFAULT_TPS
        self.ticktime = 1000 / self.__tps
        self.__t0 = self.__last_tick = ping()  # This will jumpstart the game by however long the loading time is
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
        # Populate map
        self.mod_api.spawn_map()
        for uid in range(self.unit_count):
            self._do_agent_action_phase(uid)

    # TIME MANAGEMENT
    def update(self):
        with ratecounter(self.timers['logic_total']):
            ticks = self._check_ticks()
            if self.tick == 0:
                ticks = 1
            if ticks > 0:
                self._do_ticks(ticks)

    def _check_ticks(self):
        dt = pong(self.__last_tick)
        if dt < self.ticktime or not self.auto_tick:
            return 0
        ticks = int(dt // self.ticktime)
        self.__last_tick = ping()
        dt -= ticks * self.ticktime
        self.__last_tick -= dt
        return ticks

    def _do_ticks(self, ticks):
        with ratecounter(self.timers['logic_stats']):
            hp_zero, status_zero = self.stats.do_tick(ticks)
        with ratecounter(self.timers['logic_vfx']):
            self._iterate_visual_effects(ticks)
        with ratecounter(self.timers['logic_agency']):
            self._do_agency(ticks)
            if len(hp_zero)> 0:
                for uid in hp_zero:
                    self.mod_api.hp_zero(uid)
            if len(status_zero)> 0:
                for uid, status in status_zero:
                    self.mod_api.status_zero(uid, status)

    def _iterate_visual_effects(self, ticks):
        if len(self._visual_effects) == 0:
            return
        active_effects = []
        for effect in self._visual_effects:
            effect.tick(ticks)
            if effect.active:
                active_effects.append(effect)
        self._visual_effects = active_effects

    def _do_agency(self, ticks):
        if ticks == 0:
            return
        # find which uids are in action based on distance from player
        ACTION_RADIUS = 1500
        alive = self.stats.get_stats(slice(None), STAT.HP, VALUE.CURRENT) > 0
        in_phase = alive & self._find_units_in_phase(ticks)
        in_action_radius = self.stats.get_distances(self.stats.get_position(0)) < ACTION_RADIUS
        in_action_uids = (in_phase & in_action_radius).nonzero()[0]
        if len(in_action_uids) == 0: return
        for uid in in_action_uids:
            with ratecounter(self.timers['agency_passive_single']):
                self.units[uid].do_passive(self.api)
                with ratecounter(self.timers['agency'][uid]):
                    self._do_agent_action_phase(uid)

    def _do_agent_action_phase(self, uid):
        abilities = self.units[uid].action_phase()
        if abilities is None: return
        for ability, target in abilities:
            self.use_ability(ability, target, uid)

    def _find_units_in_phase(self, ticks):
        if ticks >= self.AGENCY_PHASE_COUNT:
            # Without crashing, assume tick count is lower than phase count
            # This will not break the engine, but may cause game mechanics to break
            # Better to adjust the phase count or improve performance of game mechanics,
            # than to try and overcompute with an FPS deficiency
            logger.critical(f'Running at extremely low logic update/agency phase count ratio (requested to produce {ticks} ticks worth of agency using only {self.AGENCY_PHASE_COUNT} phases). Things are breaking.')

        # find which uids have agency in the given tick window
        phase_first = (self.tick - ticks + 1) % self.AGENCY_PHASE_COUNT
        phase_last = (self.tick) % self.AGENCY_PHASE_COUNT
        unit_agency_phases = np.arange(self.unit_count) % self.AGENCY_PHASE_COUNT
        if ticks == 1:
            return unit_agency_phases == phase_last
        # unit's phase must be between first and last (logical and)
        if phase_first < phase_last:
            return (phase_first <= unit_agency_phases) & (unit_agency_phases <= phase_last)
        # unless we wrapped around from phase count to 0 (logical or)
        return (phase_first <= unit_agency_phases) | (unit_agency_phases <= phase_last)

    # UNIT MANAGEMENT
    @property
    def tick(self):
        return self.stats.tick

    @property
    def target_tps(self):
        return self.__tps

    def add_unit(self, unit_cls, name, stats, setup_params):
        uid = self.stats.add_unit(stats)
        assert uid == len(self.units)
        unit = unit_cls(self.api, uid, name, setup_params)
        self.units.append(unit)
        return unit

    def _create_player(self, player_abilities):
        stats = self.mod_api.player_stats
        player = self.add_unit(self.mod_api.player_class, 'Player', stats, setup_params=None)
        logger.info(f'Encounter initializing player abilities: {player_abilities}')
        player.set_abilities(player_abilities)
        player.allegiance = 0
        logger.info(f'Set player allegiance as {player.allegiance}')

    # UTILITY
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

    @property
    def unit_count(self):
        return len(self.units)

    def add_visual_effect(self, *args, **kwargs):
        # logger.debug(f'Adding visual effect with: {args} {kwargs}')
        self._visual_effects.append(VisualEffect(*args, **kwargs))

    def get_visual_effects(self):
        return self._visual_effects

    def debug_action(self, *args, dev_mode=-1, tick=None, tps=None, **kwargs):
        logger.debug(f'Debug action called (extra args: {args} {kwargs})')
        if dev_mode == -1:
            dev_mode = self.dev_mode
        elif dev_mode == None:
            dev_mode = not self.dev_mode
        self.dev_mode = dev_mode
        if tick is not None:
            self._do_ticks(tick)
        if tps is not None:
            self.set_tps(tps)
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
