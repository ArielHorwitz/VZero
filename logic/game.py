import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import statistics
from nutil.vars import modify_color, List
from nutil.time import humanize_ms
from nutil.random import Seed
from nutil.file import file_dump
from data import DEV_BUILD
from data.load import RDF
from data.assets import Assets
from data.settings import Settings
from logic.common import *
from gui.api import SpriteLabel, SpriteTitleLabel, SpriteBox
from gui.api import ControlEvent

from logic.abilities import ABILITIES
from logic.encounter import EncounterAPI, DIFFICULTY_LEVELS


EncounterParams = namedtuple('EncounterParams', [
    'replayable', 'map', 'difficulty', 'vp_reward',
    'color', 'sprite', 'description',
])


class GameAPI:
    def __init__(self, interface):
        self.seed = Seed('dev')
        self.generate_world()
        self.selected_encounter = 0
        self.gui = interface
        self.encounter_api = None
        self.draftables = []
        for aid in AID_LIST:
            if not ABILITIES[aid].draftable and not Settings.get_setting('dev_build', 'General'):
                continue
            self.draftables.append(aid)
        self.loadout = [None for _ in range(8)]

    def update(self):
        self.gui.request('set_title_text', '[b]Drafting Phase[/b]' if self.encounter_api is None else '[b]Encounter in progress[/b]')

        # Handle GUI event queue
        event_queue = self.gui.get_flush_queue()
        for event in event_queue:
            self.__handle_event(event)

    def setup(self):
        logger.info(f'GLogic found gui interface:\n{self.gui.requests}')
        self.set_widgets()
        self.load_loadout(1)

    def generate_world(self):
        self.silver_bank = 1000
        self.victory_points = 0
        maps = ['default', '4c']
        vp_rewards = [0, 5, 20, 50]
        colors = [COLOR.WHITE, COLOR.YELLOW, COLOR.CYAN, COLOR.PURPLE]
        self.world_encounters = []
        self.expired_encounters = set()
        for map in maps:
            desc = '\n'.join([
                f'Sandbox: no rewards, replayable.',
                f'Map: {map}'
            ])
            self.world_encounters.append(EncounterParams(
                replayable=True, map=map, difficulty=0, vp_reward=0,
                color=modify_color(colors[0], v=0.3), sprite=str(Assets.FALLBACK_SPRITE),
                description=desc,
            ))
        replayable = False
        for difficulty_index, count in ((1, 20), (2, 10), (3, 5)):
            for i in range(count):
                map = self.seed.choice(maps)
                color = modify_color(colors[difficulty_index], v=0.3)
                sprite = Assets.get_sprite('unit', 'repteye' if map == '4c' else 'player')
                vp_reward = vp_rewards[difficulty_index]
                desc = '\n'.join([
                    f'{DIFFICULTY_LEVELS[difficulty_index]}',
                    f'Map: {map.capitalize()}',
                    f'Reward: {vp_reward} Victory Points',
                ])
                self.world_encounters.append(EncounterParams(
                    replayable, map, difficulty_index, vp_reward,
                    color, sprite, desc,
                ))
        assert len(self.world_encounters) > 0

    # Encounter management
    def restart_encounter(self):
        self.leave_encounter()
        self.new_encounter()

    def new_encounter(self):
        if self.encounter_api is None:
            if self.selected_encounter in self.expired_encounters:
                logger.info(f'GLogic requested to start new encounter {self.selected_encounter}, but already expired: {self.expired_encounters}')
                Assets.play_sfx('target', 'ui')
                return
            if self.silver_bank < self.average_draft_cost():
                logger.info(f'GLogic requested to start new encounter with {self.silver_bank} silver, but draft costs: {self.average_draft_cost()}')
                Assets.play_sfx('cost', 'ui')
                return
            ep = self.world_encounters[self.selected_encounter]
            logger.info(f'GLogic creating encounter with params: {ep} and loadout: {self.loadout}')
            if not ep.replayable:
                self.expired_encounters.add(self.selected_encounter)
            self.silver_bank -= self.average_draft_cost()
            self.refresh_world()
            self.encounter_api = EncounterAPI(self, ep, self.loadout)
            self.gui.request('start_encounter', self.encounter_api)
        else:
            logger.info(f'GLogic requested to start new encounter, but one already exists: {self.encounter_api}')
            Assets.play_sfx('target', 'ui')

    def leave_encounter(self):
        if self.encounter_api is not None:
            logger.info(f'GLogic ending encounter: {self.encounter_api}')
            win, ep = self.encounter_api.leave()
            if win:
                self.victory_points += ep.vp_reward
            self.encounter_api = None
            self.gui.request('end_encounter')
            self.gui.request('set_view', 'world')
            self.refresh_world()
        else:
            logger.warning(f'GLogic requested to end encounter but none exists')

    # Drafting
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

    def draft(self, aid):
        if aid in self.loadout:
            i = self.loadout.index(aid)
            self.loadout[i] = None
            Assets.play_sfx('ui', 'select')
            self.refresh_draft_gui()
            return

        if ABILITIES[aid].draftable or DEV_BUILD:
            for i, loadout_aid in enumerate(self.loadout):
                if loadout_aid is None:
                    self.loadout[i] = aid
                    ABILITIES[aid].play_sfx(volume='ui')
                    self.refresh_draft_gui()
                    return
        Assets.play_sfx('ui', 'target')

    # Loadouts
    @staticmethod
    def get_user_loadouts():
        Settings.reload_settings()
        if 'Loadouts' in Settings.USER_SETTINGS:
            return Settings.USER_SETTINGS['Loadouts'].default.positional
        file_dump(RDF.CONFIG_DIR / 'settings.cfg', '\n\n\n=== Loadouts\n', clear=False)
        Settings.reload_settings()
        return []

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
        self.refresh_draft_gui()

    # GUI
    def set_widgets(self):
        self.refresh_world()

    def refresh_world(self):
        sbs = []
        for i, p in enumerate(self.world_encounters):
            sbs.append(SpriteBox(
                p.sprite, p.map, p.color,
                (0,0,0,0.9) if i in self.expired_encounters else (0,0,0,0),
            ))
        self.gui.request('set_world_stack', sbs)
        self.gui.request('set_world_details', SpriteTitleLabel(
            Assets.get_sprite('ability', 'vzero'), 'World', self.world_label, (0.25, 0, 0.5, 1)))
        self.refresh_draft_gui()

    def refresh_draft_gui(self):
        draft_stack = []
        for aid in self.draftables:
            ability = ABILITIES[aid]
            name = ability.name
            drafted = ability.aid in self.loadout
            bg_color = modify_color(ability.color, v=0 if drafted else 0.7)
            fg_color = modify_color(COLOR.BLACK, a=0.7 if drafted else 0.2)
            sl = SpriteBox(ability.sprite, str(ability.draft_cost), bg_color, fg_color)
            draft_stack.append(sl)
        self.gui.request('set_draft_stack', draft_stack)

        loadout_stack = []
        for aid in self.loadout:
            if aid is None:
                sprite = Assets.get_sprite('ui', 'blank')
                s = ''
                color = (0.1,0.1,0.1,1)
            else:
                ability = ABILITIES[aid]
                sprite = ability.sprite
                s = f'{ability.name}\n({ability.draft_cost})'
                color = modify_color(ability.color, v=0.4)
            loadout_stack.append(SpriteLabel(sprite, s, color))
        self.gui.request('set_loadout_stack', loadout_stack)

        ep = self.world_encounters[self.selected_encounter]
        self.gui.request('set_draft_details', SpriteTitleLabel(
            ep.sprite,
            'Encounter details',
            '\n'.join([
                ep.description,
                f'\n__ Draft details __',
                f'Draft cost: {round(self.average_draft_cost())} silver',
                f'Silver bank: {self.silver_bank}',
                ]),
            ep.color,
        ))

        self.gui.request('set_draft_control_buttons', [
            SpriteLabel(ep.sprite, f'Play encounter', None),
            SpriteLabel(Assets.get_sprite('ability', 'vzero'), f'Return to world', None),
        ])

    @property
    def world_label(self):
        return '\n'.join([
            f'Victory Points: {self.victory_points}',
            f'Silver bank: {self.silver_bank}',
        ])

    # GUI event handlers
    def __handle_event(self, event):
        logger.debug(f'Game received event: {event}')
        handler_name = f'handle_{event.name}'
        if not hasattr(self, handler_name):
            logger.warning(f'GLogic missing handler for: {event.name}. Event: {event}')
            return
        handler = getattr(self, handler_name)
        handler(event)

    def handle_leave_encounter(self, event):
        self.leave_encounter()

    def handle_restart_encounter(self, event):
        self.restart_encounter()

    def handle_world_control_button(self, event):
        # if event.index == 0:
        #     self.gui.request('set_view', 'draft')
        # else:
        #     logger.warning(f'Unknown world control index: {event}')
        pass

    def handle_world_stack_activate(self, event):
        self.selected_encounter = event.index
        self.refresh_draft_gui()
        self.gui.request('set_view', 'draft')

    def handle_world_stack_inspect(self, event):
        ep = self.world_encounters[event.index]
        self.gui.request('activate_tooltip', SpriteTitleLabel(ep.sprite, ep.map, ep.description, None))

    def handle_draft_activate(self, event):
        self.draft(self.draftables[event.index])

    def handle_draft_inspect(self, event):
        aid = self.draftables[event.index]
        ability = ABILITIES[aid]
        ability.play_sfx(volume='ui')
        self.gui.request('activate_tooltip', SpriteTitleLabel(
            ability.sprite,
            f'{ability.name}\nDraft cost: {ability.draft_cost}',
            ability.universal_description,
            (0,0,0,0)))

    def handle_draft_control_button(self, event):
        if event.index == 0:
            self.new_encounter()
        elif event.index == 1:
            self.gui.request('set_view', 'world')

    def handle_loadout_activate(self, event):
        aid = self.loadout[event.index]
        if aid is not None:
            self.draft(aid)

    def handle_loadout_inspect(self, event):
        aid = self.loadout[event.index]
        if aid:
            ability = ABILITIES[aid]
            ability.play_sfx(volume='ui')
            self.gui.request('activate_tooltip', SpriteTitleLabel(
                ability.sprite,
                f'{ability.name}\nDraft cost: {ability.draft_cost}',
                ability.universal_description,
                (0,0,0,0)
            ))

    def handle_loadout_drag_drop(self, event):
        origin, target = event.index
        if origin != target:
            List.swap(self.loadout, origin, target)
            Assets.play_sfx('ui', 'select')
            self.refresh_draft_gui()

    def handle_save_loadout(self, event):
        loadout_str = ', '.join(['null' if aid is None else aid.name.lower() for aid in self.loadout])
        all_loadouts = self.get_user_loadouts()
        logger.info(f'Saving loadout: {loadout_str}, all loadouts:\n{all_loadouts}')
        if loadout_str not in all_loadouts:
            file_dump(RDF.CONFIG_DIR / 'settings.cfg', '\n'+loadout_str+'\n', clear=False)
            Assets.play_sfx('ui', 'pause')

    def handle_select_preset(self, event):
        Assets.play_sfx('ui', 'select')
        self.load_loadout(event.index)
