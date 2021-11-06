
from logic.mechanics.common import *
from logic.units.unit import Unit
import math
from nutil.time import ping, pong
from nutil.random import SEED


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


UNIT_TYPES = {
    'roamer': Roamer,
}
