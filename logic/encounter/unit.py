
import numpy as np
from nutil.random import SEED
from nutil.ntime import ping, pong


class Unit:
    STARTING_STATS = np.array([10, 50])

    def __init__(self, api, index, allegience):
        self.name = 'Unnamed unit'
        self.index = index
        self.allegience = allegience
        self.startup(api)

    def startup(self, api):
        pass

    def poll_abilities(self, api):
        return None


class Player(Unit):
    STARTING_STATS = np.array([10, 100])

    def startup(self, api):
        self.name = 'Player'


class RoamingMonster(Unit):
    STARTING_STATS = np.array([8, 20])

    def startup(self, api):
        self.name = 'Roaming monster'
        self.last_move = ping()
        self.next_move = 0

    def poll_abilities(self, api):
        dt = pong(self.last_move)
        if dt < self.next_move:
            return None
        self.last_move = ping()
        self.next_move = SEED.r * 10000
        if SEED.r < 0.5:
            return [(0, api.random_location())]
        else:
            return [(1, (0, 0))]


class CampMonster(Unit):
    STARTING_STATS = np.array([15, 60])

    def startup(self, api):
        self.name = 'Camp monster'
