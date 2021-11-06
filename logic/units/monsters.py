
from logic.mechanics.common import *
from logic.units.unit import Unit
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
        self.color_code = 1
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
                abilities.append((ABILITIES.ATTACK, player_pos + (SEED.r, SEED.r)))
            if player_dist < self.__aggro_range and not self.__deaggro:
                abilities.append((ABILITIES.MOVE, player_pos))
                camp_dist = math.dist(my_pos, self.camp)
                if camp_dist > self.__deaggro_range:
                    self.__deaggro = True
            else:
                if self.__deaggro is True:
                    camp_dist = math.dist(my_pos, self.camp)
                    if camp_dist < self.__reaggro_range:
                        self.__deaggro = False
                abilities.append((ABILITIES.MOVE, self.camp+RNG.random(2) * self.__camp_spread))
        return abilities


class Roamer(Unit):
    def setup(self, api,
              aggro_range=0,
              ):
        self.color_code = 2
        self.__aggro_range = float(aggro_range)
        self.last_move = ping() - (SEED.r * 5000)
        self.__last_move_location = api.random_location()

    def poll_abilities(self, api):
        my_pos = api.get_position(self.uid)
        abilities = [(ABILITIES.ATTACK, my_pos)]
        player_pos = api.get_position(0)
        if math.dist(player_pos, my_pos) < self.__aggro_range:
            target = player_pos + (SEED.r, SEED.r)
        elif pong(self.last_move) > 10000:
            self.last_move = ping()
            target = self.__last_move_location = api.random_location()
        else:
            target = self.__last_move_location
        abilities.append((ABILITIES.MOVE, target))
        return abilities


class Treasure(Unit):
    def startup(self, api, name='Loot me!'):
        self.name = name



UNIT_TYPES = {
    'camper': Camper,
    'roamer': Roamer,
    'treasure': Treasure,
}
