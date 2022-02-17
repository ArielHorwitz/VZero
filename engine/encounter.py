import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
from collections import defaultdict
from nutil.vars import NP
from nutil.time import ping, pong, RateCounter, pingpong, ratecounter
from nutil.random import Seed
from data.settings import Settings
from engine.stats import UnitStats
from engine.common import *


class Encounter:
    AGENCY_PHASE_COUNT = 30

    def __init__(self, logic):
        # Variable initialization
        self.logic = logic
        self.__seed = Seed()
        self.eid = self.__seed.r
        self.timers = defaultdict(RateCounter)
        self.timers['agency'] = defaultdict(lambda: RateCounter(sample_size=10))
        self.auto_tick = True
        self.ticktime = 1000 / TPS
        self.__t0 = self.__last_tick = ping()
        self.stats = UnitStats()
        self.units = []
        self.__active_uids = np.array([])
        self._visual_effects = []
        logger.info(f'Initialized Encounter Engine {self}')

    # TIME MANAGEMENT
    def update(self, active_uids):
        assert isinstance(active_uids, np.ndarray)
        assert len(active_uids) == self.unit_count
        self.__active_uids = active_uids
        with ratecounter(self.timers['logic_total']):
            if self.tick == 0:
                logger.info(f'Encounter {self.eid} started.')
                ticks = 1
            ticks = self._check_ticks()
            if ticks > self.AGENCY_PHASE_COUNT:
                logger.info(f'Requested {ticks} ticks on a single frame, throttled to {self.AGENCY_PHASE_COUNT}.')
                ticks = self.AGENCY_PHASE_COUNT
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
            hp_zero, status_zero, cooldown_zero = self.stats.do_tick(ticks)
        with ratecounter(self.timers['logic_vfx']):
            self._iterate_visual_effects(ticks)
        with ratecounter(self.timers['logic_agency']):
            self._do_agency(ticks)
            if len(hp_zero) > 0:
                for uid in hp_zero:
                    self.logic.hp_zero(uid)
            if len(status_zero) > 0:
                for uid, status in status_zero:
                    self.logic.status_zero(uid, status)
            if len(cooldown_zero) > 0:
                for uid, aid in cooldown_zero:
                    self.units[uid].off_cooldown(aid)
        with ratecounter(self.timers['logic_valuecap']):
            self.stats._cap_minmax_values()

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
        # find which uids are in action based on phase
        alive = self.stats.get_stats(slice(None), STAT.HP, VALUE.CURRENT) > 0
        in_phase = alive & self._find_units_in_phase(ticks)
        in_action_uids = np.flatnonzero(in_phase & self.__active_uids)
        if len(in_action_uids) == 0: return
        for uid in in_action_uids:
            with ratecounter(self.timers['agency'][uid]):
                self._do_agent_action_phase(uid)

    def _do_agent_action_phase(self, uid):
        self.units[uid].passive_phase()
        self.units[uid].action_phase()

    def _find_units_in_phase(self, ticks):
        if ticks > self.AGENCY_PHASE_COUNT:
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

    @property
    def tick(self):
        return self.stats.tick

    def set_auto_tick(self, auto=None):
        if auto is None:
            auto = not self.auto_tick
        self.auto_tick = auto
        self.__last_tick = ping()
        logger.info(f'Set auto tick: {self.auto_tick}')
        return self.auto_tick

    # UNIT MANAGEMENT
    @property
    def next_uid(self):
        return len(self.units)

    def add_unit(self, unit, stats=None):
        index = self.stats.add_unit(stats)
        assert unit.uid == index == len(self.units)
        self.units.append(unit)

    @property
    def unit_count(self):
        return len(self.units)

    # UTILITY
    def add_visual_effect(self, *args, **kwargs):
        self._visual_effects.append(VisualEffect(*args, **kwargs))

    def get_visual_effects(self):
        return self._visual_effects

    # STATS API
    @property
    def get_stats(self):
        return self.stats.get_stats

    @property
    def set_stats(self):
        return self.stats.set_stats

    @property
    def get_delta_total(self):
        return self.stats.get_delta_total

    @property
    def get_dmod(self):
        return self.stats.get_dmod

    @property
    def kill_statuses(self):
        return self.stats.kill_statuses

    @property
    def kill_dmods(self):
        return self.stats.kill_dmods

    @property
    def get_status(self):
        return self.stats.get_status

    @property
    def set_status(self):
        return self.stats.set_status

    @property
    def get_cooldown(self):
        return self.stats.get_cooldown

    @property
    def set_cooldown(self):
        return self.stats.set_cooldown

    @property
    def get_position(self):
        return self.stats.get_position

    @property
    def set_position(self):
        return self.stats.set_position

    @property
    def get_positions(self):
        return self.stats.get_positions

    @property
    def set_positions(self):
        return self.stats.set_positions

    @property
    def align_to_target(self):
        return self.stats.align_to_target

    @property
    def get_velocity(self):
        return self.stats.get_velocity

    @property
    def set_move(self):
        return self.stats.set_move

    @property
    def get_distances(self):
        return self.stats.get_distances

    @property
    def get_distance(self):
        return self.stats.get_distance

    @property
    def unit_distance(self):
        return self.stats.unit_distance

    def mask_alive(self):
        return self.stats.get_stats(slice(None), STAT.HP) > 0

    def mask_dead(self):
        return np.invert(self.mask_alive())

    def nearest_uid(self, point, mask=None, alive_only=True):
        if mask is None:
            mask = np.ones(len(self.units), dtype=np.bool)
        if alive_only:
            mask = np.logical_and(mask, self.get_stats(slice(None), STAT.HP) > 0)
        if mask.sum() == 0:
            return None, None
        distances = self.stats.get_distances(point)
        uid = NP.argmin(distances, mask)
        return uid, distances[uid]

    @property
    def set_collision(self):
        return self.stats.set_collision

    @property
    def add_dmod(self):
        return self.stats.add_dmod

    @property
    def unmoveable_mask(self):
        return self.stats.get_stats(slice(None), STAT.WEIGHT) < 0
