
import math, copy
import numpy as np
from nutil.time import ping, pong
from nutil.random import SEED
from logic.encounter.common import *


RNG = np.random.default_rng()


class Unit:
    HITBOX = 20
    def __init__(self, api, uid, allegience, name=None):
        self.uid = uid
        self._name = 'Unnamed unit' if name is None else name
        self.allegience = allegience
        self.color_code = 1
        self.startup(api)

    @property
    def name(self):
        return f'{self._name} ({self.uid})'

    def startup(self, api):
        pass

    def poll_abilities(self, api):
        return None


class Player(Unit):
    SPRITE = 'robot-1.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 0},
        STAT.HP: {VALUE.CURRENT: 100, VALUE.MAX_VALUE: 100, VALUE.DELTA: 0.02},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 1},
        STAT.MANA: {VALUE.CURRENT: 100, VALUE.MAX_VALUE: 100, VALUE.DELTA: 0.2},
        STAT.RANGE: {VALUE.CURRENT: 100},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
        STAT.ATTACK_DELAY_COST: {VALUE.CURRENT: 100},
    }

    def startup(self, api):
        self._name = 'Player'
        self.color_code = 0


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
    def reaggro_range(self):
        return 100

    @property
    def deaggro_range(self):
        return 800

    @property
    def aggro_range(self):
        return 300

    @property
    def camp_spread(self):
        return 50


class BloodImp(Camping):
    SPRITE = 'flying-blood.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 5},
        STAT.HP: {VALUE.CURRENT: 40, VALUE.MAX_VALUE: 40, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.6},
        STAT.MANA: {VALUE.CURRENT: 10, VALUE.MAX_VALUE: 10, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 150},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
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
        STAT.HP: {VALUE.CURRENT: 85, VALUE.MAX_VALUE: 85, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.2},
        STAT.MANA: {VALUE.CURRENT: 20, VALUE.MAX_VALUE: 20, VALUE.DELTA: 0.25},
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
        STAT.MANA: {VALUE.CURRENT: 20, VALUE.MAX_VALUE: 20, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 300},
        STAT.DAMAGE: {VALUE.CURRENT: 20},
        STAT.ATTACK_DELAY_COST: {VALUE.CURRENT: 50},
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
        STAT.MOVE_SPEED: {VALUE.CURRENT: 1.2},
        STAT.MANA: {VALUE.CURRENT: 10, VALUE.MAX_VALUE: 10, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 80},
        STAT.DAMAGE: {VALUE.CURRENT: 10},
        STAT.ATTACK_DELAY_COST: {VALUE.CURRENT: 50},
    }

    def startup(self, api):
        self._name = 'Zen Rat'
        self.color_code = 4

    @property
    def aggro_range(self):
        return 140


# ROAMERS
class Roaming(Unit):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.last_move = ping() - (SEED.r * 5000)
        self.__last_move_location = k['api'].random_location()

    def poll_abilities(self, api):
        my_pos = api.get_position(self.uid)
        abilities = [(ABILITIES.ATTACK, my_pos)]
        player_pos = api.get_position(0)
        if math.dist(player_pos, my_pos) < self.aggro_range:
            target = player_pos + (SEED.r, SEED.r)
        elif pong(self.last_move) > 10000:
            self.last_move = ping()
            target = self.__last_move_location = api.random_location()
        else:
            target = self.__last_move_location
        abilities.append((ABILITIES.MOVE, target))
        return abilities

    @property
    def aggro_range(self):
        return 0


class FireElemental(Roaming):
    SPRITE = 'fire-elemental.png'
    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 20},
        STAT.HP: {VALUE.CURRENT: 220, VALUE.MAX_VALUE: 180, VALUE.DELTA: 0.05},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.7},
        STAT.MANA: {VALUE.CURRENT: 20, VALUE.MAX_VALUE: 20, VALUE.DELTA: 0.25},
        STAT.RANGE: {VALUE.CURRENT: 90},
        STAT.DAMAGE: {VALUE.CURRENT: 80},
    }

    def startup(self, api):
        self._name = 'Fire Elemental'
        self.color_code = 2

    @property
    def aggro_range(self):
        return 250


DEFAULT_STARTING_STATS = {
    STAT.POS_X: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.POS_Y: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: -1_000_000_000,
        VALUE.MAX_VALUE: 1_000_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.GOLD: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.HP: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: 0,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MOVE_SPEED: {
        VALUE.CURRENT: 1,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.MANA: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_00,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.RANGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.DAMAGE: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1,
        VALUE.TARGET_TICK: 0,
    },
    STAT.ATTACK_DELAY: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: -1,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.ATTACK_DELAY_COST: {
        VALUE.CURRENT: 200,
        VALUE.MIN_VALUE: 10,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: 0,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.BLOODLUST_LIFESTEAL: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: -1,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
    STAT.BLOODLUST_COOLDOWN: {
        VALUE.CURRENT: 0,
        VALUE.MIN_VALUE: 0,
        VALUE.MAX_VALUE: 1_000_000,
        VALUE.DELTA: -1,
        VALUE.TARGET_VALUE: -1_000_000,
        VALUE.TARGET_TICK: 0,
    },
}


SPAWN_WEIGHTS = {
    Ratzan: (6, 6),
    BloodImp: (6, 4),
    NullIce: (3, 1),
    FireElemental: (2, 1),
    WingedSnake: (0, 1),
}


def get_starting_stats(base=None, custom=None):
    stats = copy.deepcopy(DEFAULT_STARTING_STATS if base is None else base)
    if custom is not None:
        for stat in STAT:
            if stat in custom:
                for value in VALUE:
                    if value in custom[stat]:
                        stats[stat][value] = custom[stat][value]
    return stats
