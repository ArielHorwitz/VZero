import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import itertools
import math
import numpy as np
import random
from nutil.vars import normalize, collide_point
from nutil.time import ping, pong
from nutil.random import SEED

from logic.mechanics.common import *
from logic.mechanics.unit import Unit as BaseUnit
from logic.mechanics.player import Player as BasePlayer
from logic.mechanics import import_mod_module as import_
ICAT = import_('items.items').ITEM_CATEGORIES


RNG = np.random.default_rng()



class Unit(BaseUnit):
    _respawn_timer = 14400  # ~ 2 minutes

    def setup(self, **params):
        self.p = params
        self._respawn_location = self.api.get_position(self.uid)
        self._respawn_gold = self.api.get_stats(self.uid, STAT.GOLD)
        self._setup()

    @property
    def is_alive(self):
        return self.api.get_stats(self.uid, STAT.HP) > 0

    def _setup(self):
        pass

    def hp_zero(self):
        self._respawn_gold = self.api.get_stats(self.uid, STAT.GOLD)
        self.api.set_status(self.uid, STATUS.RESPAWN, self._respawn_timer, 1)

    def status_zero(self, status):
        if status is STATUS.RESPAWN:
            self.respawn()

    def respawn(self, reset_gold=True):
        logger.debug(f'{self.name} {self.uid} respawned')
        max_hp = self.api.get_stats(self.uid, STAT.HP, VALUE.MAX_VALUE)
        self.api.set_stats(self.uid, STAT.HP, max_hp)
        max_mana = self.api.get_stats(self.uid, STAT.MANA, VALUE.MAX_VALUE)
        self.api.set_stats(self.uid, STAT.MANA, max_mana)
        self.api.set_position(self.uid, self._respawn_location, halt=True)
        if reset_gold:
            self.api.set_stats(self.uid, STAT.GOLD, self._respawn_gold)


class Player(BasePlayer, Unit):
    _respawn_timer = 1200

    def setup(self, **params):
        super(BasePlayer, self).setup(**params)
        super(Unit, self).setup(**params)

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
        self.api.set_stats(self.uid, STAT.HP, 0)
        self.api.set_status(self.uid, STATUS.RESPAWN,
            self._respawn_timer - self.WAVE_INTERVAL + 1, 1)

    @property
    def target(self):
        ws = self.WAVE_SPREAD
        return self.api.map_size/2 + (RNG.random(2)*ws-(ws/2))

    def respawn(self):
        super().respawn()
        self.scale_power()
        spawn_point = self._respawn_location + (RNG.random(2)*self.WAVE_SPREAD-(self.WAVE_SPREAD/2))
        self.api.set_position(self.uid, spawn_point)
        self.api.use_ability(ABILITY.WALK, self.target, self.uid)

    def scale_power(self):
        self.api.set_stats(self.uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER, STAT.GOLD,
        ], self.scaling, multiplicative=True)

    @property
    def _respawn_timer(self):
        return self.wave_offset + self.WAVE_INTERVAL - self.api.tick % self.WAVE_INTERVAL

    def poll_abilities(self, api):
        return [
            (ABILITY.ATTACK, self.api.get_position(self.uid)),
            (ABILITY.WALK, self.target),
        ]

    @property
    def debug_str(self):
        return f'Spawned at: {self._respawn_location}\nNext wave: {self._respawn_timer}'


class Camper(Unit):
    def _setup(self):
        self.color = (1, 0, 0)
        self.camp = self.api.get_position(self.uid)
        self.__aggro_range = float(self.p['aggro_range'])
        self.__deaggro_range = float(self.p['deaggro_range'])
        self.__reaggro_range = float(self.p['reaggro_range'])
        self.__camp_spread = float(self.p['camp_spread'])
        self.__deaggro = False
        self.__walk_target = self.camp
        self.__next_walk = self.api.tick

    def poll_abilities(self, api):
        player_pos = self.api.get_position(0)
        abilities = [(ABILITY.ATTACK, player_pos)]
        my_pos = self.api.get_position(self.uid)
        in_aggro_range = math.dist(my_pos, player_pos) < self.__aggro_range
        if in_aggro_range and not self.__deaggro and self.api.units[0].is_alive:
            abilities.append((ABILITY.WALK, player_pos))
            camp_dist = math.dist(my_pos, self.camp)
            if camp_dist > self.__deaggro_range:
                self.__deaggro = True
        else:
            if self.__deaggro is True:
                camp_dist = math.dist(my_pos, self.camp)
                if camp_dist < self.__reaggro_range:
                    self.__deaggro = False
            abilities.append((ABILITY.WALK, self.walk_target))
        return abilities

    @property
    def walk_target(self):
        if self.__next_walk <= self.api.tick:
            self.__walk_target = self.camp+(RNG.random(2) * self.__camp_spread*2 - self.__camp_spread)
            self.__next_walk = self.api.tick + SEED.r * 500
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
        self.api.set_stats(self.uid, STAT.HP, 1_000_000, value_name=VALUE.MAX_VALUE)
        self.api.set_stats(self.uid, STAT.HP, 1_000_000, value_name=VALUE.DELTA)
        self.api.set_stats(self.uid, STAT.WEIGHT, -1)

    def poll_abilities(self, api):
        self.api.set_status(self.uid, STATUS.SHOP, duration=0, stacks=self.category.value)
        return [(ABILITY.SHOPKEEPER, self.api.get_position(self.uid))]

    @property
    def sprite(self):
        return f'shop-{self.category.name.lower()}'


class Fountain(Unit):
    def _setup(self):
        self.abilities.append(ABILITY.FOUNTAIN_HP)
        self.abilities.append(ABILITY.FOUNTAIN_MANA)
        self.api.set_stats(self.uid, STAT.WEIGHT, -1)


class DPSMeter(Unit):
    def _setup(self):
        self.api.set_stats(self.uid, STAT.HP, 10**12, value_name=VALUE.MAX_VALUE)
        self.api.set_stats(self.uid, STAT.HP, 10**12)
        self.api.set_stats(self.uid, STAT.HP, 0, value_name=VALUE.DELTA)
        self.__started = False
        self.__sample_size = 10
        self.__sample_index = 0
        self.__sample = np.ndarray((self.__sample_size, 2), dtype = np.float64)
        self.__last_tick = self.api.tick
        self.__last_hp = self.api.get_stats(self.uid, STAT.HP)
        self.__tps = 120

    def poll_abilities(self, api):
        new_hp = self.api.get_stats(self.uid, STAT.HP)
        self.__sample_index += 1
        self.__sample_index %= self.__sample_size
        sample_time = self.api.tick - self.__last_tick
        self.__last_tick = self.api.tick
        sample_damage = self.__last_hp - new_hp
        self.__last_hp = new_hp
        self.__sample[self.__sample_index] = (sample_time, sample_damage)

    @property
    def debug_str(self):
        total_time = self.__sample[:, 0].sum()
        total_damage = self.__sample[:, 1].sum()
        dps = total_damage / total_time
        return f'DPS: {dps*self.__tps:.2f} ({total_damage:.2f} / {total_time:.2f}) [{self.__sample_index}]'
