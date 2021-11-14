
from logic.mechanics.common import *
from logic.mechanics.unit import Unit
import math
import numpy as np
from nutil.time import ping, pong
from nutil.random import SEED

RNG = np.random.default_rng()


class Camper(Unit):
    def setup(self, api,
              aggro_range=0,
              deaggro_range=800,
              reaggro_range=100,
              camp_spread=50,
              ):
        self.color = (1, 0, 0)
        self.__aggro_range = float(aggro_range)
        self.__deaggro_range = float(deaggro_range)
        self.__reaggro_range = float(reaggro_range)
        self.__camp_spread = float(camp_spread)
        self.__deaggro = False
        self.last_move = ping() - (SEED.r * 5000)
        self.camp = api.get_position(self.uid)

    def poll_abilities(self, api):
        abilities = []
        if pong(self.last_move) > 500:
            self.last_move = ping()
            my_pos = api.get_position(self.uid)
            player_pos = api.get_position(0)
            player_dist = math.dist(player_pos, my_pos)
            if player_dist < api.get_stats(self.uid, STAT.RANGE, VALUE.CURRENT):
                abilities.append((ABILITY.ATTACK, player_pos + (SEED.r, SEED.r)))
            if player_dist < self.__aggro_range and not self.__deaggro:
                abilities.append((ABILITY.MOVE, player_pos))
                camp_dist = math.dist(my_pos, self.camp)
                if camp_dist > self.__deaggro_range:
                    self.__deaggro = True
            else:
                if self.__deaggro is True:
                    camp_dist = math.dist(my_pos, self.camp)
                    if camp_dist < self.__reaggro_range:
                        self.__deaggro = False
                abilities.append((ABILITY.MOVE, self.camp+RNG.random(2) * self.__camp_spread))
        return abilities


class Roamer(Unit):
    def setup(self, api,
              aggro_range=0,
              ):
        self.color = (0, 0, 1)
        self.__aggro_range = float(aggro_range)
        self.last_move = ping() - (SEED.r * 5000)
        self.__last_move_location = api.random_location()

    def poll_abilities(self, api):
        my_pos = api.get_position(self.uid)
        abilities = [(ABILITY.ATTACK, my_pos)]
        player_pos = api.get_position(0)
        if math.dist(player_pos, my_pos) < self.__aggro_range:
            target = player_pos + (SEED.r, SEED.r)
        elif pong(self.last_move) > 10000:
            self.last_move = ping()
            target = self.__last_move_location = api.random_location()
        else:
            target = self.__last_move_location
        abilities.append((ABILITY.MOVE, target))
        return abilities


class Treasure(Unit):
    def setup(self, api, name='Loot me!'):
        self.name = name


class DPSMeter(Unit):
    def setup(self, api, name='Hit me!'):
        self.name = name
        api.set_stats(self.uid, STAT.HP, 10**12, value_name=VALUE.MAX_VALUE)
        api.set_stats(self.uid, STAT.HP, 10**12)
        api.set_stats(self.uid, STAT.HP, 0, value_name=VALUE.DELTA)
        self.__started = False
        self.__sample_size = 10
        self.__sample_index = 0
        self.__sample = np.ndarray((self.__sample_size, 2), dtype = np.float64)
        self.__last_tick = api.tick
        self.__last_hp = api.get_stats(self.uid, STAT.HP)
        self.__tps = 120

    def poll_abilities(self, api):
        new_hp = api.get_stats(self.uid, STAT.HP)
        self.__sample_index += 1
        self.__sample_index %= self.__sample_size
        sample_time = api.tick - self.__last_tick
        self.__last_tick = api.tick
        sample_damage = self.__last_hp - new_hp
        self.__last_hp = new_hp
        self.__sample[self.__sample_index] = (sample_time, sample_damage)

    @property
    def debug_str(self):
        total_time = self.__sample[:, 0].sum()
        total_damage = self.__sample[:, 1].sum()
        dps = total_damage / total_time
        return f'DPS: {dps*self.__tps:.2f} ({total_damage:.2f} / {total_time:.2f}) [{self.__sample_index}]'


UNIT_TYPES = {
    'camper': Camper,
    'roamer': Roamer,
    'treasure': Treasure,
    'dps_meter': DPSMeter,
}
