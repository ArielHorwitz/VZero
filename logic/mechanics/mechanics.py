import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data.load import RDF
from data.assets import Assets
from logic.mechanics import import_mod_module
from logic.mechanics.common import *
from logic.mechanics.mod import ModEncounterAPI
mod_definitions = import_mod_module('definitions')
logger.info(f'Imported mod definitions: {mod_definitions}')



class __Mechanics:
    def __init__(self):
        self.mod_encounter_api_cls = mod_definitions.EncounterAPI
        assert issubclass(self.mod_encounter_api_cls, ModEncounterAPI)
        self.abilities = self.__load_abilities(RDF.load(RDF.CONFIG_DIR / 'abilities.bal'))

    def cast_ability(self, aid, api, uid, target):
        if uid == 0:
            logger.debug(f'uid {uid} casting ability {aid.name} to {target}')
        ability = self.abilities[aid]
        r = ability.cast(api, uid, target)
        if r is None:
            m = f'Ability {ability.__class__} cast() method returned None. Must return FAIL_RESULT on fail or aid on success.'
            logger.error(m)
            raise ValueError(m)
        if isinstance(r, FAIL_RESULT):
            logger.debug(f'uid {uid} tried casting {aid.name} but failed with {r.name}')
        else:
            if Assets.get_sfx('ability', ability.name, allow_exception=False) is not None:
                api.add_visual_effect(VisualEffect.SFX, 5, params={'sfx': ability.name, 'call_source': (uid, aid, __name__)})
        return r

    @property
    def ability_classes(self):
        return mod_definitions.ABILITY_CLASSES

    def __load_abilities(self, raw_data):
        abilities = []
        raw_items = tuple(raw_data.items())
        for aid in ABILITY:
            ability_name, ability_data = raw_items[aid]
            ability_type = ability_data[0][0][0]
            stats = {}
            if 'stats' in ability_data:
                stats = ability_data['stats']
                del stats[0]
            ability_instance = self.ability_classes[ability_type](
                aid, ability_name, stats)
            assert len(abilities) == aid
            abilities.append(ability_instance)
            logger.info(f'Loaded ability: {aid} {ability_name} {ability_data}')
        return abilities


Mechanics = __Mechanics()
