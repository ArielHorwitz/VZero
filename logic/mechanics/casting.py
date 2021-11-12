
from nutil.display import adis
from data.load import load_abilities
from logic.mechanics.common import *
from logic.mechanics.abilities import ABILITY_TYPES

import logging
logger = logging.getLogger(__name__)

class Cast:
    ABILITY_INSTANCES = {}
    __ABILITY_DATA = load_abilities()
    logger.info(f'Loading casting abilities:')
    for aid in ABILITIES:
        internal_name = aid.name
        if internal_name not in __ABILITY_DATA:
            raise RuntimeError(f'I don\'t know how we got here. Missing implementation for ability {aid.name}')
        data = __ABILITY_DATA[internal_name]
        logger.info(f'{internal_name} {data["name"]} ({data["type"]}): {data["params"]}')
        full_name = data['name']
        ability_type = data['type']
        params = data['params']
        ability_cls = ABILITY_TYPES[ability_type]
        ability = ability_cls(aid, full_name, **params)
        ABILITY_INSTANCES[aid] = ability

    @classmethod
    def cast_ability(cls, aid, api, uid, target):
        callback = cls.ABILITY_INSTANCES[aid].cast
        r = callback(api, uid, target)
        return r
