
from logic.mechanics.common import *
from logic.units import Unit
import math
from nutil.time import ping, pong
from nutil.random import SEED



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
        STAT.RANGE: {VALUE.CURRENT: 90},
        STAT.DAMAGE: {VALUE.CURRENT: 80},
    }

    def startup(self, api):
        self._name = 'Fire Elemental'
        self.color_code = 2

    @property
    def aggro_range(self):
        return 250


class Folphin(Roaming):
    SPRITE = 'folphin.png'

    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 30},
        STAT.HP: {VALUE.CURRENT: 150, VALUE.MAX_VALUE: 150, VALUE.TARGET_VALUE: 30, VALUE.DELTA: -0.001},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0.5, VALUE.MAX_VALUE: 1, VALUE.DELTA: 0.001},
        STAT.RANGE: {VALUE.CURRENT: 90},
        STAT.DAMAGE: {VALUE.CURRENT: 30},
        STAT.ATTACK_SPEED: {VALUE.CURRENT: 50, VALUE.MAX_VALUE: 200, VALUE.DELTA: 0.001},
    }

    def startup(self, api):
        self._name = 'Folphin The Flaming Mammal'
        self.color_code = 9

    @property
    def aggro_range(self):
        return 250


class Treasure(Unit):
    SPRITE = 'camp.png'

    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 200},
        STAT.HP: {VALUE.CURRENT: 300, VALUE.MAX_VALUE: 300 ,VALUE.DELTA: 1},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0},
        STAT.RANGE: {VALUE.CURRENT: 20},
        STAT.DAMAGE: {VALUE.CURRENT: 40},
    }

    def startup(self, api):
        self._name = 'LOOT ME!!!'


class HerosTreasure(Unit):
    SPRITE = 'goal.png'

    STARTING_STATS = {
        STAT.GOLD: {VALUE.CURRENT: 400},
        STAT.HP: {VALUE.CURRENT: 400, VALUE.MAX_VALUE: 400 ,VALUE.DELTA: 2},
        STAT.MOVE_SPEED: {VALUE.CURRENT: 0},
        STAT.RANGE: {VALUE.CURRENT: 20},
        STAT.DAMAGE: {VALUE.CURRENT: 100},
    }

    def startup(self, api):
        self._name = 'Try To Pull Me Out'


UNITS = {
    'fire-elemental': FireElemental,
    'folphin': Folphin,
    'treasure': Treasure,
    'heros-treasure': HerosTreasure,
}
