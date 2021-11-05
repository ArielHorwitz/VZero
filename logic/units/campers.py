
from logic.mechanics.common import *
from logic.units import Unit
import math
import numpy as np
from nutil.time import ping, pong
from nutil.random import SEED

RNG = np.random.default_rng()


# CAMPERS
class Camping(Unit):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.last_move = ping() - (SEED.r * 5000)
        self.camp = k['api'].get_position(self.uid)
        self.__deaggro = False

    def poll_abilities(self, api):
        abilities = []
        if pong(self.last_move) > 500:
            self.last_move = ping()
            my_pos = api.get_position(self.uid)
            player_pos = api.get_position(0)
            player_dist = math.dist(player_pos, my_pos)
            if player_dist < api.get_stats(self.uid, STAT.RANGE, VALUE.CURRENT):
                abilities.append((ABILITIES.ATTACK, player_pos + (SEED.r, SEED.r)))
            if player_dist < self.aggro_range and not self.__deaggro:
                abilities.append((ABILITIES.MOVE, player_pos))
                camp_dist = math.dist(my_pos, self.camp)
                if camp_dist > self.deaggro_range:
                    self.__deaggro = True
            else:
                if self.__deaggro is True:
                    camp_dist = math.dist(my_pos, self.camp)
                    if camp_dist < self.reaggro_range:
                        self.__deaggro = False
                abilities.append((ABILITIES.MOVE, self.camp+RNG.random(2) * self.camp_spread))
        return abilities

    @property
    def aggro_range(self):
        return 300

    @property
    def deaggro_range(self):
        return 800

    @property
    def reaggro_range(self):
        return 100

    @property
    def camp_spread(self):
        return 50


class BloodImp(Camping):
    SPRITE = 'flying-blood.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 5},
        STAT.HP: {VALUE.CURRENT: 40, VALUE.MAX_VALUE: 40, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.6},
        STAT.RANGE: {VALUE.CURRENT: 150},
        STAT.DAMAGE: {VALUE.CURRENT: 15},
        STAT.ATTACK_SPEED: {VALUE.CURRENT: 80},
    }

    def startup(self, api):
        self._name = 'Blood Imp'
        self.color_code = 1

    @property
    def aggro_range(self):
        return 350


class NullIce(Camping):
    SPRITE = 'null-tri.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 10},
        STAT.HP: {VALUE.CURRENT: 60, VALUE.MAX_VALUE: 60, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.2},
        STAT.RANGE: {VALUE.CURRENT: 200},
        STAT.DAMAGE: {VALUE.CURRENT: 40},
    }

    def startup(self, api):
        self._name = 'Null Ice'
        self.color_code = 3

    @property
    def aggro_range(self):
        return 0


class WingedSnake(Camping):
    SPRITE = 'winged-snake.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 100},
        STAT.HP: {VALUE.CURRENT: 400, VALUE.MAX_VALUE: 400, VALUE.DELTA: 0.15},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.2},
        STAT.RANGE: {VALUE.CURRENT: 300},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
        STAT.ATTACK_SPEED: {VALUE.CURRENT: 200},
    }

    def startup(self, api):
        self._name = 'Winged Snake'
        self.color_code = 5

    @property
    def aggro_range(self):
        return 0


class Ratzan(Camping):
    SPRITE = 'ratzan.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 5},
        STAT.HP: {VALUE.CURRENT: 30, VALUE.MAX_VALUE: 30, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 1.2, VALUE.MAX_VALUE:3, VALUE.DELTA: 0.0001},
        STAT.RANGE: {VALUE.CURRENT: 100, VALUE.MIN_VALUE: 30, VALUE.DELTA: -0.001},
        STAT.DAMAGE: {VALUE.CURRENT: 10},
        STAT.ATTACK_SPEED: {VALUE.CURRENT: 200},
    }

    def startup(self, api):
        self._name = 'Ratzan'
        self.color_code = 4

    @property
    def aggro_range(self):
        return 140


UNITS = {
    'blood-imp': BloodImp,
    'null-ice': NullIce,
    'winged-snake': WingedSnake,
    'ratzan': Ratzan,
}
