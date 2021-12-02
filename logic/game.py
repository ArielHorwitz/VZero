import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from nutil.vars import modify_color
from data.load import RDF
from data.assets import Assets
from data.settings import Settings
from engine.common import *
from engine.api import GameAPI as BaseGameAPI
from gui.api import SpriteLabel
from logic.encounter import EncounterAPI
from logic.abilities._release import ABILITY_CLASSES


class GameAPI(BaseGameAPI):
    def __init__(self):
        self.abilities = self.__load_abilities(RDF.load(RDF.CONFIG_DIR / 'abilities.rdf'))
        self.loadout = [_ for _ in range(8)]
        self.selected_aid = 0

    def select_ability(self, aid):
        if aid is None:
            return
        self.selected_aid = aid
        Assets.play_sfx('ability', self.abilities[aid].name,
                        volume=Settings.get_volume('ui'),
                        allow_exception=False)

    def draft(self, aid):
        if aid in self.loadout:
            i = self.loadout.index(aid)
            self.loadout[i] = None
            Assets.play_sfx('ui', 'select', volume=Settings.get_volume('ui'))
            return

        for i, loadout_aid in enumerate(self.loadout):
            if loadout_aid is None:
                self.loadout[i] = aid
                Assets.play_sfx('ability', self.abilities[aid].name, volume=Settings.get_volume('ui'))
                return
        else:
            Assets.play_sfx('ui', 'target', volume=Settings.get_volume('ui'))

    # GUI handlers
    def new_encounter(self):
        if self.encounter_api is None:
            self.encounter_api = EncounterAPI(self, self.loadout)

    def draft_click(self, aid, button):
        if button == 'left':
            self.select_ability(aid)
        if button == 'right':
            self.draft(aid)

    def loadout_click(self, index, button):
        if button == 'left':
            self.select_ability(self.loadout[index])
        if button == 'right':
            aid = self.loadout[index]
            self.draft(aid)

    # GUI properties
    def draft_info_box(self):
        ability = self.abilities[self.selected_aid]
        return SpriteLabel(Assets.get_sprite('ability', ability.sprite), ability.name, modify_color(ability.color, a=0.5))

    def draft_info_label(self):
        ability = self.abilities[self.selected_aid]
        return ability.general_description

    def draft_boxes(self):
        b = []
        for ability in self.abilities:
            a = 0.4 if ability.aid not in self.loadout else 0
            sl = SpriteLabel(Assets.get_sprite('ability', ability.sprite), ability.name, (*ability.color[:3], a))
            b.append(sl)
        return b

    def loadout_boxes(self):
        b = []
        for aid in self.loadout:
            if aid is None:
                b.append(SpriteLabel(str(Assets.FALLBACK_SPRITE), '', (0, 0, 0, 0.5)))
            else:
                ability = self.abilities[aid]
                b.append(SpriteLabel(Assets.get_sprite('ability', ability.sprite), ability.name, (*ability.color[:3], 0.4)))
        return b

    # Misc
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
            ability_instance = ABILITY_CLASSES[ability_type](
                aid, ability_name, stats)
            assert len(abilities) == aid
            abilities.append(ability_instance)
            logger.info(f'Loaded ability: {aid} {ability_name} {ability_data}')
        return abilities
