import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import statistics
from nutil.vars import modify_color, List
from nutil.time import humanize_ms
from nutil.file import file_dump
from data import DEV_BUILD
from data.load import RDF
from data.assets import Assets
from data.settings import Settings
from engine.common import *
from engine.api import GameAPI as BaseGameAPI
from gui.api import SpriteLabel, SpriteTitleLabel, SpriteBox

from logic.data import ABILITIES
from logic.encounter import EncounterAPI


class GameAPI(BaseGameAPI):
    difficulty_levels = EncounterAPI.difficulty_levels

    def __init__(self):
        self.restart_difficulty_flag = None
        self.silver_bank = 1000
        self.draftables = []
        for aid in AID_LIST:
            if not ABILITIES[aid].draftable and not Settings.get_setting('dev_build', 'General'):
                continue
            self.draftables.append(aid)
        self.loadout = [None for _ in range(8)]
        self.selected_aid = self.draftables[0]
        self.load_loadout(1)

    def update(self):
        if self.restart_difficulty_flag is not None:
            difficulty = self.restart_difficulty_flag
            self.restart_difficulty_flag = None
            self.new_encounter(difficulty)

    def average_draft_cost(self, loadout=None):
        if loadout is None:
            loadout = self.loadout
        s = list(ABILITIES[a].draft_cost for a in loadout if a is not None)
        return statistics.mean(s) if len(s) > 0 else 0

    def draft_cost_minutes(self, draft_cost=None):
        if draft_cost is None:
            draft_cost = self.average_draft_cost()
        extra_minutes = draft_cost / 5
        return max(0, extra_minutes - 6)

    def calc_score(self, draft_cost, elapsed_minutes):
        total_penalty = elapsed_minutes + self.draft_cost_minutes(draft_cost)
        return int(1000 * 50 / (50+total_penalty))

    def select_ability(self, aid):
        self.selected_aid = aid
        ABILITIES[self.selected_aid].play_sfx(volume='ui')

    def draft(self, aid):
        if aid in self.loadout:
            i = self.loadout.index(aid)
            self.loadout[i] = None
            Assets.play_sfx('ui', 'select')
            return

        if ABILITIES[aid].draftable or DEV_BUILD:
            for i, loadout_aid in enumerate(self.loadout):
                if loadout_aid is None:
                    self.loadout[i] = aid
                    ABILITIES[aid].play_sfx(volume='ui')
                    return
        Assets.play_sfx('ui', 'target')

    # GUI handlers
    button_names = []

    @property
    def title_text(self):
        return '\n'.join([
            f'Silver bank: {self.silver_bank}',
        ])

    def restart_encounter(self):
        self.restart_difficulty_flag = self.encounter_api.difficulty_level
        self.leave_encounter()

    def new_encounter(self, difficulty_level=0):
        if self.encounter_api is None:
            logger.info(f'Logic creating encounter with loadout: {self.loadout}')
            self.encounter_api = EncounterAPI(self, difficulty_level, self.loadout)

    def leave_encounter(self):
        if self.encounter_api is not None:
            logger.info(f'Logic ending encounter: {self.encounter_api}')
            self.encounter_api.leave()
            self.encounter_api = None

    @staticmethod
    def get_user_loadouts():
        Settings.reload_settings()
        if 'Loadouts' in Settings.USER_SETTINGS:
            return Settings.USER_SETTINGS['Loadouts'].default.positional
        file_dump(RDF.CONFIG_DIR / 'settings.cfg', '\n\n\n=== Loadouts\n', clear=False)
        Settings.reload_settings()
        return []

    def save(self):
        loadout_str = ', '.join(['null' if aid is None else aid.name.lower() for aid in self.loadout])
        all_loadouts = self.get_user_loadouts()
        logger.info(f'saving loadout: {loadout_str}, all loadouts:\n{all_loadouts}')
        if loadout_str not in all_loadouts:
            file_dump(RDF.CONFIG_DIR / 'settings.cfg', '\n'+loadout_str+'\n', clear=False)
            Assets.play_sfx('ui', 'pause')

    def load_loadout(self, loadout_number):
        if loadout_number == 0:
            self.loadout = [None for _ in range(8)]
        elif loadout_number != 0:
            self.loadout = []
            all_loadouts = self.get_user_loadouts()
            loadout_index = loadout_number - 1 if loadout_number > 0 else loadout_number
            if all_loadouts and len(all_loadouts) > loadout_index:
                selected_loadout = all_loadouts[loadout_index]
                for aname in selected_loadout.split(', '):
                    try:
                        aid = str2ability(aname)
                        assert ABILITIES[aid].draftable or DEV_BUILD
                        self.loadout.append(aid)
                    except:
                        self.loadout.append(None)
            self.loadout.extend([None for _ in range(8-len(self.loadout))])

    def number_select(self, index):
        Assets.play_sfx('ui', 'select')
        self.load_loadout(index)

    def draft_click(self, index, button):
        aid = self.draftables[index]
        if button == 'left':
            self.select_ability(aid)
        if button == 'right':
            self.draft(aid)

    def loadout_click(self, index, button):
        aid = self.loadout[index]
        if button == 'left':
            if aid is None:
                return
            self.select_ability(aid)
        if button == 'right':
            if aid is None:
                return
            self.draft(aid)

    def loadout_drag_drop(self, origin, target, button):
        if button == 'middle' and origin != target:
            List.swap(self.loadout, origin, target)
            Assets.play_sfx('ui', 'select')

    # GUI properties
    def draft_label(self):
        return f'Draft cost: {round(self.average_draft_cost())} silver'

    def draft_details(self):
        ability = ABILITIES[self.selected_aid]
        s = f'{ability.name}\nDraft cost: {ability.draft_cost}'
        color = ability.color
        return SpriteTitleLabel(
            ability.sprite,
            s, ability.universal_description,
            modify_color(color, v=0.5))

    def draft_boxes(self):
        b = []
        for aid in self.draftables:
            ability = ABILITIES[aid]
            name = ability.name
            drafted = ability.aid in self.loadout
            bg_color = modify_color(ability.color, v=0 if drafted else 0.7)
            fg_color = modify_color(COLOR.BLACK, a=0.7 if drafted else 0.2)
            sl = SpriteBox(
                ability.sprite,
                str(ability.draft_cost), bg_color, fg_color)
            b.append(sl)
        return b

    def loadout_boxes(self):
        b = []
        for aid in self.loadout:
            if aid is None:
                b.append(
                    SpriteLabel(Assets.get_sprite('ui', 'blank'),
                    '', (0,0,0,0)))
            else:
                ability = ABILITIES[aid]
                s = f'{ability.name}\n({ability.draft_cost})'
                b.append(
                    SpriteLabel(ability.sprite,
                    s, modify_color(ability.color, v=0.4)))
        return b
