import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import itertools
import math
import numpy as np
import random
from nutil.vars import normalize, collide_point
from nutil.time import ping, pong, ratecounter
from nutil.random import SEED
from data.assets import Assets
from data.settings import Settings

from engine.common import *
from engine.unit import Unit as BaseUnit
from logic.items import ITEMS, ITEM_CATEGORIES as ICAT
from logic.mechanics import Mechanics

RNG = np.random.default_rng()


class Unit(BaseUnit):
    _respawn_timer = 12000  # ~ 2 minutes
    def __init__(self, api, uid, name, params):
        super().__init__(uid, name)
        self.win_on_death = False
        self.lose_on_death = False
        self.api = api
        self.engine = api.engine
        self.name = self.__start_name = name
        self.p = params
        if 'abilities' in params:
            abilities = [str2ability(a) for a in params['abilities'].split(', ')]
        else:
            abilities = [ABILITY.WALK, ABILITY.ATTACK]
        self.abilities = abilities
        self.abilities.extend([None for i in range(8-len(self.abilities))])
        self.item_slots = [None for i in range(8)]

    def use_item(self, iid, target):
        with ratecounter(self.engine.timers['ability_single']):
            if not self.engine.auto_tick and not self.api.dev_mode:
                logger.warning(f'Unit {self.uid} tried using item {iid.name} while paused')
                return FAIL_RESULT.INACTIVE

            if not self.is_alive:
                logger.warning(f'Unit {self.uid} is dead and requested item {iid.name}')
                return FAIL_RESULT.INACTIVE

            target = np.array(target)
            if (target > self.api.map_size).any() or (target < 0).any():
                return FAIL_RESULT.OUT_OF_BOUNDS

            item = ITEMS[iid]
            r = item.cast(self.api, self.uid, target)
            if r is None:
                m = f'Item {item} ability {item.ability.__class__}.cast() method returned None. Must return FAIL_RESULT on fail or aid on success.'
                logger.warning(m)
            return r

    def use_ability(self, aid, target):
        with ratecounter(self.engine.timers['ability_single']):
            if not self.engine.auto_tick and not self.api.dev_mode:
                logger.warning(f'Unit {self.uid} tried using ability {aid.name} while paused')
                return FAIL_RESULT.INACTIVE

            if not self.is_alive:
                logger.warning(f'Unit {self.uid} is dead and requested ability {aid.name}')
                return FAIL_RESULT.INACTIVE

            target = np.array(target)
            if (target > self.api.map_size).any() or (target < 0).any():
                return FAIL_RESULT.OUT_OF_BOUNDS

            ability = self.api.abilities[aid]
            r = ability.cast(self.engine, self.uid, target)
            if r is None:
                m = f'Ability {ability.__class__}.cast() method returned None. Must return FAIL_RESULT on fail or aid on success.'
                logger.warning(m)
            return r

    def setup(self):
        self._respawn_location = self.engine.get_position(self.uid)
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self._setup()

    def passive_phase(self):
        for aid in self.abilities:
            if aid is None:
                continue
            self.api.abilities[aid].passive(self.engine, self.uid, self.engine.AGENCY_PHASE_COUNT)
        for iid in self.item_slots:
            if iid is None:
                continue
            ITEMS[iid].passive(self.engine, self.uid, self.engine.AGENCY_PHASE_COUNT)

    @property
    def sprite(self):
        return Assets.get_sprite('unit', self.__start_name)

    @property
    def size(self):
        hb = self.engine.get_stats(self.uid, STAT.HITBOX)
        return np.array([hb, hb])*2

    @property
    def is_alive(self):
        return self.engine.get_stats(self.uid, STAT.HP) > 0

    def _setup(self):
        pass

    def hp_zero(self):
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self.engine.set_status(self.uid, STATUS.RESPAWN, self._respawn_timer, 1)

    def status_zero(self, status):
        if status is STATUS.RESPAWN:
            self.respawn()

    def respawn(self, reset_gold=True):
        logger.debug(f'{self.name} {self.uid} respawned')
        max_hp = self.engine.get_stats(self.uid, STAT.HP, VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.HP, max_hp)
        max_mana = self.engine.get_stats(self.uid, STAT.MANA, VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.MANA, max_mana)
        self.engine.set_position(self.uid, self._respawn_location, halt=True)
        if reset_gold:
            self.engine.set_stats(self.uid, STAT.GOLD, self._respawn_gold)


class Player(Unit):
    _max_hp_delta_interval = 1000

    def _setup(self):
        self._respawn_timer = 500
        self._max_hp_delta = float(self.p['max_hp_delta']) * self._max_hp_delta_interval if 'max_hp_delta' in self.p else 0
        self._next_max_hp_delta = self._max_hp_delta_interval

    def passive_phase(self, *a, **k):
        if self.engine.tick >= self._next_max_hp_delta:
            self.engine.set_stats(self.uid, STAT.HP, self._max_hp_delta, value_name=VALUE.MAX, additive=True)
            self.engine.set_stats(self.uid, STAT.HP, self._max_hp_delta, additive=True)
            self._next_max_hp_delta = self._next_max_hp_delta + self._max_hp_delta_interval
        super().passive_phase(*a, **k)

    def hp_zero(self):
        logger.info(f'Player {self.name} {self.uid} died.')
        super().hp_zero()

    def respawn(self):
        logger.info(f'Player {self.name} {self.uid} respawned.')
        super().respawn(reset_gold=False)
        self._respawn_timer += 500


class Creep(Unit):
    WAVE_INTERVAL = 30000  # 5 minutes

    def _setup(self):
        self.first_wave = True
        self.color = (1, 0, 0)
        self.wave_offset = float(self.p['wave']) * self.WAVE_INTERVAL
        self.scaling = float(self.p['scaling']) if 'scaling' in self.p else 1
        # Ensure the whole wave does not spawn too close, as collision is finnicky at the time of writing
        self._respawn_location += RNG.random(2) * self.engine.get_stats(self.uid, STAT.HITBOX) * 5
        self.engine.set_position(self.uid, self._respawn_location)
        # Start the first wave on the correct interval
        self.engine.set_stats(self.uid, STAT.HP, 0)
        self.engine.set_status(self.uid, STATUS.RESPAWN,
            self._respawn_timer - self.WAVE_INTERVAL + 1, 1)

    @property
    def target(self):
        return self.engine.units[0]._respawn_location

    def respawn(self):
        super().respawn()
        if self.first_wave is False:
            self.scale_power()
        self.first_wave = False
        self.use_ability(ABILITY.WALK, self.target)

    def scale_power(self):
        currents = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.WATER, STAT.GOLD]
        deltas = maxs = [STAT.HP, STAT.MANA]
        self.engine.set_stats(self.uid, currents, self.scaling, multiplicative=True)
        self.engine.set_stats(self.uid, deltas, self.scaling, value_name=VALUE.DELTA, multiplicative=True)
        self.engine.set_stats(self.uid, maxs, self.scaling, value_name=VALUE.MAX, multiplicative=True)
        self.engine.set_stats(self.uid, maxs, 1_000_000)

    @property
    def _respawn_timer(self):
        return self.wave_offset + self.WAVE_INTERVAL - self.engine.tick % self.WAVE_INTERVAL

    def action_phase(self):
        self.use_ability(ABILITY.ATTACK, self.engine.get_position(self.uid))
        self.use_ability(ABILITY.WALK, self.target)

    @property
    def debug_str(self):
        return f'Spawned at: {self._respawn_location}\nNext wave: {self._respawn_timer}'


class Camper(Unit):
    def _setup(self):
        self.color = (1, 0, 0)
        self.camp = self.engine.get_position(self.uid)
        self.__aggro_range = float(self.p['aggro_range'])
        self.__deaggro_range = float(self.p['deaggro_range'])
        self.__reaggro_range = float(self.p['reaggro_range'])
        self.__camp_spread = float(self.p['camp_spread'])
        self.__deaggro = False
        self.__walk_target = self.camp
        self.__next_walk = self.engine.tick

    def action_phase(self):
        player_pos = self.engine.get_position(0)
        camp_dist = self.engine.get_distances(self.camp, self.uid)
        in_aggro_range = self.engine.unit_distance(self.uid, 0) < self.__aggro_range
        if in_aggro_range and not self.__deaggro and self.engine.units[0].is_alive:
            for aid in self.abilities:
                if aid is None: continue
                self.use_ability(aid, player_pos)
            if camp_dist > self.__deaggro_range:
                self.__deaggro = True
        else:
            if self.__deaggro is True and camp_dist < self.__reaggro_range:
                    self.__deaggro = False
            self.use_ability(self.abilities[0], self.walk_target)

    @property
    def walk_target(self):
        if self.__next_walk <= self.engine.tick:
            self.__walk_target = self.camp+(RNG.random(2) * self.__camp_spread*2 - self.__camp_spread)
            self.__next_walk = self.engine.tick + SEED.r * 500
        return self.__walk_target

    @property
    def debug_str(self):
        return f'Camping at: {self.camp}'


class Boss(Camper):
    def _setup(self):
        self.win_on_death = True
        super()._setup()


class Treasure(Unit):
    def _setup(self):
        self._respawn_timer = 1_000_000
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)


class Shopkeeper(Unit):
    def _setup(self):
        self.abilities = [ABILITY.SHOPKEEPER, *(None for _ in range(7))]
        category = 'BASIC' if 'category' not in self.p else self.p['category'].upper()
        for icat in ICAT:
            if category == icat.name:
                self.category = icat
                break
        else:
            raise ValueError(f'Unknown item category: {category}')
        self.name = f'{icat.name.lower().capitalize()} shop'
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)

    def action_phase(self):
        self.engine.set_status(self.uid, STATUS.SHOP, duration=0, stacks=self.category.value)


class Fountain(Unit):
    def _setup(self):
        self.abilities = [ABILITY.FOUNTAIN_HP, ABILITY.FOUNTAIN_MANA]
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)


class Fort(Fountain):
    def _setup(self):
        super()._setup()
        self.lose_on_death = True


class DPSMeter(Unit):
    def _setup(self):
        self.engine.set_stats(self.uid, STAT.HP, 10**12, value_name=VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.HP, 10**12)
        self.engine.set_stats(self.uid, STAT.HP, 0, value_name=VALUE.DELTA)
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        self.abilities = []
        self.__started = False
        self.__sample_size = 10
        self.__sample_index = 0
        self.__sample = np.zeros((self.__sample_size, 2), dtype = np.float64)
        self.__sample[0, 0] = 1
        self.__last_tick = self.engine.tick
        self.__last_hp = self.engine.get_stats(self.uid, STAT.HP)
        self.__tps = 100

    def action_phase(self):
        new_hp = self.engine.get_stats(self.uid, STAT.HP)
        self.__sample_index += 1
        self.__sample_index %= self.__sample_size
        sample_time = self.engine.tick - self.__last_tick
        self.__last_tick = self.engine.tick
        sample_damage = self.__last_hp - new_hp
        self.__last_hp = new_hp
        self.__sample[self.__sample_index] = (sample_time, sample_damage)

        total_time = self.__sample[:, 0].sum()
        total_damage = self.__sample[:, 1].sum()
        dps = total_damage / total_time
        self.name = f'DPS: {dps*self.__tps:.2f}'


UNIT_CLASSES = {
    'fort': Fort,
    'player': Player,
    'boss': Boss,
    'creep': Creep,
    'camper': Camper,
    'treasure': Treasure,
    'shopkeeper': Shopkeeper,
    'fountain': Fountain,
    'dps_meter': DPSMeter,
}
