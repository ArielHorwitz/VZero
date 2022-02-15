import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import statistics
from nutil.vars import modify_color, List
from nutil.time import humanize_ms
from data.load import RDF
from data.assets import Assets
from data.settings import Settings
from engine.common import *
from engine.api import GameAPI as BaseGameAPI
from gui.api import SpriteLabel, SpriteTitleLabel, SpriteBox

from logic.data import ABILITIES
from logic.encounter import EncounterAPI


class GameAPI(BaseGameAPI):
    def __init__(self):
        self.restart_flag = False
        self.high_score = 0
        self.draftables = []
        for aid in AID_LIST:
            if not ABILITIES[aid].draftable and not Settings.get_setting('dev_build', 'General'):
                continue
            self.draftables.append(aid)
        self.loadout = [None for _ in range(8)]
        self.selected_aid = self.draftables[0]

    def update(self):
        if self.restart_flag:
            self.restart_flag = False
            self.new_encounter()

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

    def load_preset(self, index):
        self.loadout = []
        preset_loadout = Settings.get_setting(f'preset_loadout{index+1}', 'Personal').split(', ')
        for name in preset_loadout:
            if name == 'null':
                self.loadout.append(None)
                continue
            try:
                aid = str2ability(name)
            except AttributeError as e:
                self.loadout.append(None)
                continue
            self.loadout.append(aid)
        self.loadout.extend([None for _ in range(8-len(self.loadout))])

    def select_ability(self, aid):
        self.selected_aid = aid
        ABILITIES[self.selected_aid].play_sfx(volume='ui')

    def draft(self, aid):
        if aid in self.loadout:
            i = self.loadout.index(aid)
            self.loadout[i] = None
            Assets.play_sfx('ui', 'select')
            return

        for i, loadout_aid in enumerate(self.loadout):
            if loadout_aid is None:
                self.loadout[i] = aid
                ABILITIES[aid].play_sfx(volume='ui')
                return
        else:
            Assets.play_sfx('ui', 'target')

    # GUI handlers
    button_names = ['Clear']+[f'Preset {i+1}' for i in range(4)]

    @property
    def title_text(self):
        return '\n'.join([
            f'High score: {self.high_score}',
        ])

    def restart_encounter(self):
        self.leave_encounter()
        self.restart_flag = True

    def new_encounter(self):
        if self.encounter_api is None:
            logger.info(f'Logic creating encounter with loadout: {self.loadout}')
            self.encounter_api = EncounterAPI(self, self.loadout, self.average_draft_cost())

    def leave_encounter(self):
        if self.encounter_api is not None:
            logger.info(f'Logic ending encounter: {self.encounter_api}')
            self.encounter_api.leave()
            score = self.encounter_api.score
            self.high_score = max(score, self.high_score)
            self.encounter_api = None

    def button_click(self, index):
        if index == 0:
            self.loadout = [None for _ in range(8)]
        else:
            self.load_preset(index-1)
        Assets.play_sfx('ui', 'select')

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
        dc = self.average_draft_cost()
        dcm = humanize_ms(self.draft_cost_minutes()*60*1000, show_ms=False, show_hours=False)
        return "\n".join([
            f'___ Score Calculation _______',
            f'Draft cost: {dcm} (average ability: {round(dc, 1)})',
            f'Starting score: {self.calc_score(dc, 0)}',
            'Time:  '+' / '.join(f'{n}m' for n in range(5, 35, 5)),
            'Score: '+' /  '.join(f'{self.calc_score(dc, n)}' for n in range(5, 35, 5)),
        ])

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
