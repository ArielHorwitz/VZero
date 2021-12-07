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
from logic.items import ITEM_CATEGORIES as ICAT


RNG = np.random.default_rng()


class Unit(BaseUnit):
    _respawn_timer = 14400  # ~ 2 minutes
    def __init__(self, api, uid, name, params):
        super().__init__(uid, name)
        self.api = api
        self.engine = api.engine
        self.name = self.__start_name = name
        self.abilities = []
        self.items = []
        self.p = params
        self.allegiance = 1

    def use_ability(self, aid, target):
        with ratecounter(self.engine.timers['ability_single']):
            if not self.engine.auto_tick and not self.api.dev_mode:
                return FAIL_RESULT.INACTIVE

            if not self.is_alive:
                logger.warning(f'Unit {uid} is dead and requested ability {aid.name}')
                return FAIL_RESULT.INACTIVE

            target = np.array(target)
            if (target > self.api.map_size).any() or (target < 0).any():
                return FAIL_RESULT.OUT_OF_BOUNDS

            ability = self.api.abilities[aid]
            r = ability.cast(self.engine, self.uid, target)
            if r is None:
                m = f'Ability {ability.__class__} cast() method returned None. Must return FAIL_RESULT on fail or aid on success.'
                logger.error(m)
                raise ValueError(m)
            if not isinstance(r, FAIL_RESULT):
                Assets.play_sfx('ability', ability.name, volume=Settings.get_volume('sfx'))
            return r

    def setup(self):
        self._respawn_location = self.engine.get_position(self.uid)
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self._setup()

    def passive_phase(self):
        if len(self.abilities) == 0:
            return
        for aid in self.abilities:
            self.api.abilities[aid].passive(self.engine, self.uid, self.engine.AGENCY_PHASE_COUNT)

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
    _respawn_timer = 1200
    allegiance = 0

    def hp_zero(self):
        logger.info(f'Player {self.name} {self.uid} died.')
        super().hp_zero()

    def respawn(self):
        logger.info(f'Player {self.name} {self.uid} respawned.')
        super().respawn(reset_gold=False)


class Creep(Unit):
    WAVE_SPREAD = 200
    WAVE_INTERVAL = 28_800  # 4 minutes

    def _setup(self):
        self.color = (1, 0, 0)
        self.wave_offset = float(self.p['wave']) * self.WAVE_INTERVAL
        self.scaling = float(self.p['scaling']) if 'scaling' in self.p else 1.05
        # Start the first wave on the correct interval
        self.engine.set_stats(self.uid, STAT.HP, 0)
        self.engine.set_status(self.uid, STATUS.RESPAWN,
            self._respawn_timer - self.WAVE_INTERVAL + 1, 1)

    @property
    def target(self):
        ws = self.WAVE_SPREAD
        return self.api.map_size/2 + (RNG.random(2)*ws-(ws/2))

    def respawn(self):
        super().respawn()
        self.scale_power()
        spawn_point = self._respawn_location + (RNG.random(2)*self.WAVE_SPREAD-(self.WAVE_SPREAD/2))
        self.engine.set_position(self.uid, spawn_point)
        self.use_ability(ABILITY.WALK, self.target)

    def scale_power(self):
        self.engine.set_stats(self.uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER, STAT.GOLD,
        ], self.scaling, multiplicative=True)

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
        self.use_ability(ABILITY.ATTACK, player_pos)
        my_pos = self.engine.get_position(self.uid)
        in_aggro_range = math.dist(my_pos, player_pos) < self.__aggro_range
        if in_aggro_range and not self.__deaggro and self.engine.units[0].is_alive:
            self.use_ability(ABILITY.WALK, player_pos)
            camp_dist = math.dist(my_pos, self.camp)
            if camp_dist > self.__deaggro_range:
                self.__deaggro = True
        else:
            if self.__deaggro is True:
                camp_dist = math.dist(my_pos, self.camp)
                if camp_dist < self.__reaggro_range:
                    self.__deaggro = False
            self.use_ability(ABILITY.WALK, self.walk_target)

    @property
    def walk_target(self):
        if self.__next_walk <= self.engine.tick:
            self.__walk_target = self.camp+(RNG.random(2) * self.__camp_spread*2 - self.__camp_spread)
            self.__next_walk = self.engine.tick + SEED.r * 500
        return self.__walk_target

    @property
    def debug_str(self):
        return f'Camping at: {self.camp}'


class Treasure(Unit):
    pass


class Shopkeeper(Unit):
    def _setup(self):
        category = 'BASIC' if 'category' not in self.p else self.p['category'].upper()
        for icat in ICAT:
            if category == icat.name:
                self.category = icat
                break
        else:
            raise ValueError(f'Unknown item category: {category}')
        self.name = f'{icat.name.lower().capitalize()} shop'
        # self.engine.set_stats(self.uid, STAT.HP, 10, value_name=VALUE.MAX)
        # self.engine.set_stats(self.uid, STAT.HP, 1_000_000, value_name=VALUE.DELTA)
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)

    def action_phase(self):
        self.engine.set_status(self.uid, STATUS.SHOP, duration=0, stacks=self.category.value)
        self.use_ability(ABILITY.SHOPKEEPER, self.engine.get_position(self.uid))


class Fountain(Unit):
    def _setup(self):
        self.abilities.append(ABILITY.FOUNTAIN_HP)
        self.abilities.append(ABILITY.FOUNTAIN_MANA)
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)


class DPSMeter(Unit):
    def _setup(self):
        self.engine.set_stats(self.uid, STAT.HP, 10**12, value_name=VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.HP, 10**12)
        self.engine.set_stats(self.uid, STAT.HP, 0, value_name=VALUE.DELTA)
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        self.__started = False
        self.__sample_size = 10
        self.__sample_index = 0
        self.__sample = np.zeros((self.__sample_size, 2), dtype = np.float64)
        self.__sample[0, 0] = 1
        self.__last_tick = self.engine.tick
        self.__last_hp = self.engine.get_stats(self.uid, STAT.HP)
        self.__tps = 120

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
        self.name = f'DPS: {dps*self.__tps:.2f} ({total_damage:.2f} / {total_time:.2f}) [{self.__sample_index}]'


UNIT_CLASSES = {
    'player': Player,
    'creep': Creep,
    'camper': Camper,
    'treasure': Treasure,
    'shopkeeper': Shopkeeper,
    'fountain': Fountain,
    'dps_meter': DPSMeter,
}
