
from nutil.display import adis
from data.load import load_abilities
from logic.mechanics.common import *
from logic.mechanics.abilities import DefaultAbilities, ABILITY_TYPES


class Cast:
    ABILITY_INSTANCES = {}
    __ABILITY_DATA = load_abilities()
    print(f'Loading casting abilities:')
    for aid in ABILITIES:
        internal_name = aid.name
        if internal_name not in __ABILITY_DATA:
            print(f'{internal_name} not found in loaded abilities, using default.')
            continue
        data = __ABILITY_DATA[internal_name]
        print(f'{internal_name} {data["name"]} ({data["type"]}): {data["params"]}')
        full_name = data['name']
        ability_type = data['type']
        params = data['params']
        ability_cls = ABILITY_TYPES[ability_type]
        ability = ability_cls(aid, full_name, **params)
        ABILITY_INSTANCES[aid] = ability

    @classmethod
    def cast_ability(cls, aid, api, uid, target):
        if aid in cls.ABILITY_INSTANCES:
            callback = cls.ABILITY_INSTANCES[aid].cast
        else:
            callback = getattr(DefaultAbilities, f'{aid.name.lower()}')
        r = callback(api, uid, target)
        return r
