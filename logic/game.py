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

from logic.data import ABILITIES
from logic.encounter import EncounterAPI
from logic.base import Ability


class GameAPI(BaseGameAPI):
    def __init__(self):
        self.loadout = [_ for _ in range(8)]
        self.selected_aid = list(ABILITY)[0]

    def select_ability(self, aid):
        if aid is None:
            return
        aid = AID_LIST[aid]
        self.selected_aid = aid
        Assets.play_sfx('ability', aid.name,
                        volume=Settings.get_volume('ui'),
                        allow_exception=False)

    def draft(self, aid):
        aid = AID_LIST[aid]
        if aid in self.loadout:
            i = self.loadout.index(aid)
            self.loadout[i] = None
            Assets.play_sfx('ui', 'select', volume=Settings.get_volume('ui'))
            return

        for i, loadout_aid in enumerate(self.loadout):
            if loadout_aid is None:
                self.loadout[i] = aid
                Assets.play_sfx('ability', aid.name, volume=Settings.get_volume('ui'))
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
        ability = ABILITIES[self.selected_aid]
        name = ability.name
        color = ability.color
        return SpriteLabel(Assets.get_sprite('ability', name), name, modify_color(color, a=0.5))

    def draft_info_label(self):
        return ABILITIES[self.selected_aid].universal_description

    def draft_boxes(self):
        b = []
        for ability in ABILITIES:
            name = ability.name
            a = 0.7 if ability.aid not in self.loadout else 0.15
            sl = SpriteLabel(Assets.get_sprite('ability', name), name, (*ability.color, a))
            b.append(sl)
        return b

    def loadout_boxes(self):
        b = []
        for aid in self.loadout:
            if aid is None:
                b.append(SpriteLabel(str(Assets.FALLBACK_SPRITE), '', (0, 0, 0, 0.5)))
            else:
                ability = ABILITIES[aid]
                name = ability.name
                b.append(SpriteLabel(Assets.get_sprite('ability', name), name, (*ability.color, 0.4)))
        return b
