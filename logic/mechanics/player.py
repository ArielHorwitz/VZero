import logging
logger = logging.getLogger(__name__)
# setLevel(logging.DEBUG)

import math
import numpy as np
from logic.mechanics.unit import Unit
from logic.mechanics.common import *

class Player(Unit):
    def setup(self, api, **params):
        self.color = (0, 1, 0)
        self.preferred_target = None
        self.last_attack = api.tick - 100
        self.targeting_rate = 10
        self.abilities = []
        self.ability_order = []

    def set_abilities(self, aids):
        self.ability_order = aids
        logger.info(f'{self.name} loaded abilities:')
        for aid in aids:
            if aid not in self.abilities and aid is not None:
                logger.info(aid.name.lower().capitalize())
                self.abilities.append(aid)

    def use_ability(self, api, aid, target):
        if aid not in self.abilities:
            logger.warning(f'{self.name} trying to use ability {aid.name} without access:\nAbility access: {tuple(_.name for _ in self.abilities)}')
            return
        r = api.use_ability(aid, target, self.uid)
        return r