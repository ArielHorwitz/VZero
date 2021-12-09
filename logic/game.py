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
        self.draftables = []
        for aid in AID_LIST:
            if not ABILITIES[aid].draftable and not Settings.get_setting('dev_build', 'General'):
                continue
            self.draftables.append(aid)
        self.loadout = [None for _ in range(8)]
        self.selected_aid = AID_LIST[0]
        self.load_preset(0)

    def load_preset(self, index):
        self.loadout = []
        preset_loadout = Settings.get_setting(f'preset_loadout{index+1}', 'Personal').split(', ')
        for name in preset_loadout:
            if name == 'null':
                self.loadout.append(None)
                continue
            aid = str2ability(name)
            self.loadout.append(aid)
        self.loadout.extend([None for _ in range(8-len(self.loadout))])

    def select_ability(self, aid):
        if aid is None:
            return
        aid = AID_LIST[aid]
        self.selected_aid = aid
        ABILITIES[self.selected_aid].play_sfx(volume='ui')

    def draft(self, aid):
        if aid is None:
            return
        aid = AID_LIST[aid]
        if aid in self.loadout:
            i = self.loadout.index(aid)
            self.loadout[i] = None
            Assets.play_sfx('ui', 'select', volume='ui')
            return

        for i, loadout_aid in enumerate(self.loadout):
            if loadout_aid is None:
                self.loadout[i] = aid
                Assets.play_sfx('ability', aid.name, volume='ui')
                return
        else:
            Assets.play_sfx('ui', 'target', volume='ui')

    # GUI handlers
    button_names = ['Clear']+[f'Preset {i+1}' for i in range(4)]

    def button_click(self, index):
        if index == 0:
            self.loadout = [None for _ in range(8)]
        else:
            self.load_preset(index-1)
        Assets.play_sfx('ui', 'select', volume=Settings.get_volume('ui'))

    def new_encounter(self):
        if self.encounter_api is None:
            logger.info(f'Creating encounter with loadout: {self.loadout}')
            self.encounter_api = EncounterAPI(self, self.loadout)

    def draft_click(self, index, button):
        aid = self.draftables[index]
        if button == 'left':
            self.select_ability(index)
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
        for aid in self.draftables:
            ability = ABILITIES[aid]
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
