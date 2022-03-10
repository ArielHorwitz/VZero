import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import statistics
from nutil.vars import modify_color, List
from nutil.time import humanize_ms
from nutil.random import Seed
from nutil.file import file_dump
from data.load import RDF
from data.assets import Assets
from data.settings import PROFILE, DEV_BUILD
from logic.mapgen import MAP_DATA
from logic.common import *
from gui.api import SpriteLabel, SpriteTitleLabel, SpriteBox
from gui.api import ControlEvent

from logic.abilities import ABILITIES
from logic.encounter import EncounterAPI, DIFFICULTY_LEVELS, METAGAME_BALANCE_SHORT


EncounterParams = namedtuple('EncounterParams', [
    'replayable', 'silver_cost', 'map', 'difficulty', 'vp_reward',
    'color', 'sprite', 'description',
])


class GameAPI:
    def __init__(self, interface, settings_notifier):
        self.gui = interface
        self.settings_notifier = settings_notifier
        self.seed = Seed('dev')
        self.selected_encounter = 0
        self.encounter_api = None
        self.draftables = []
        self.loadout = [None for _ in range(8)]
        self.generate_world()
        self.settings_notifier.subscribe('misc.debug_mode', self.setting_debug_mode)

    def setting_debug_mode(self):
        self.refresh_world()

    def update(self):
        self.refresh_title_text()

        # Handle GUI event queue
        event_queue = self.gui.get_flush_queue()
        for event in event_queue:
            self.__handle_event(event)

    def setup(self):
        logger.info(f'GLogic found gui interface:\n{self.gui.requests}')
        self.set_widgets()
        # self.load_loadout(1)

    def generate_world(self):
        self.silver_bank = 1000
        self.victory_points = 0
        counts = [1, 3, 2, 1, 1]
        replayable = [True, False, False, False, False]
        silver_cost = [False, True, True, True, True]
        vp_rewards = [0, 5, 10, 20, 50]
        colors = [COLOR.WHITE, COLOR.YELLOW, COLOR.CYAN, COLOR.PURPLE, COLOR.RED]
        self.world_encounters = []
        self.expired_encounters = set()
        for i in range(1):
            for j in range(counts[i]):
                for map in MAP_DATA:
                    logger.info(f'Loading map: {map}')
                    if i > 0 and 'devtest' in map.lower():
                        continue
                    metadata = MAP_DATA[map]['map']['Metadata'].default
                    map_name = metadata['name']
                    map_desc = metadata['description'] if 'description' in metadata else ''
                    color = modify_color(colors[i], v=0.3)
                    sprite_name = metadata['sprite'] if 'sprite' in metadata else f'maps.{map}'
                    sprite = Assets.get_sprite(sprite_name)
                    vp_reward = vp_rewards[i]
                    desc = '\n'.join([
                        map_desc,
                        f'Difficulty: {DIFFICULTY_LEVELS[i]}',
                        'Draft costs silver' if silver_cost[i] else 'Free play',
                        'Replayable' if replayable[i] else 'Non-replayable',
                        f'Map: {map_name}',
                        f'Reward: {vp_reward} Victory Points',
                    ])
                    self.world_encounters.append(EncounterParams(
                        replayable=replayable[i], silver_cost=silver_cost[i],
                        map=map, difficulty=i, vp_reward=vp_rewards[i],
                        color=modify_color(colors[i], v=0.3),
                        sprite=sprite,
                        description=desc,
                    ))
        assert len(self.world_encounters) > 0

    # Encounter management
    def new_encounter(self):
        if self.encounter_api is None:
            if self.selected_encounter in self.expired_encounters:
                logger.info(f'GLogic requested to start new encounter {self.selected_encounter}, but already expired: {self.expired_encounters}')
                Assets.play_sfx('ui.target', volume='ui')
                return
            if self.silver_bank < self.average_draft_cost():
                logger.info(f'GLogic requested to start new encounter with {self.silver_bank} silver, but draft costs: {self.average_draft_cost()}')
                Assets.play_sfx('ui.cost', volume='ui')
                return
            ep = self.world_encounters[self.selected_encounter]
            logger.info(f'GLogic creating encounter with params: {ep} and loadout: {self.loadout}')
            if not ep.replayable:
                self.expired_encounters.add(self.selected_encounter)
            if ep.silver_cost:
                self.silver_bank -= self.average_draft_cost()
            self.encounter_api = EncounterAPI(self, ep, self.loadout)
            self.gui.request('start_encounter', self.encounter_api)
            self.refresh_world()
        else:
            logger.info(f'GLogic requested to start new encounter, but one already exists: {self.encounter_api}')
            Assets.play_sfx('ui.target', volume='ui')
            self.gui.request('switch_screen', 'encounter')

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
            Assets.play_sfx('ui.select', volume='ui')
            self.refresh_draft_gui()
            return

        if aid in self.draftables:
            for i, loadout_aid in enumerate(self.loadout):
                if loadout_aid is None:
                    self.loadout[i] = aid
                    ABILITIES[aid].play_sfx(volume='ui')
                    self.refresh_draft_gui()
                    return
        Assets.play_sfx('ui.target', volume='ui')

    # GUI
    def set_widgets(self):
        self.refresh_world()

    def refresh_title_text(self):
        if self.encounter_api is None:
            view = self.gui.request('get_view')
            if view == 'world':
                title_text = 'Map Selection'
            elif view == 'draft':
                title_text = 'Drafting Phase'
            else:
                title_text = ''
        else:
            title_text = 'Encounter in progress'
        self.gui.request('set_title_text', f'[b]{title_text}[/b]')

    def refresh_world(self):
        sbs = []
        label = ''
        for i, p in enumerate(self.world_encounters):
            sbs.append(SpriteBox(
                p.sprite, label, p.color,
                (0,0,0,0.9) if i in self.expired_encounters else (0,0,0,0),
            ))
        self.gui.request('set_world_stack', sbs)
        self.gui.request('set_world_details', SpriteTitleLabel(
            Assets.get_sprite('abilities.vzero'), 'World', self.world_label, (0.25, 0, 0.5, 1)))

        if self.encounter_api is not None:
            s = self.encounter_api.encounter_params.sprite
            world_controls = [SpriteLabel(s, f'Encounter in progress!', None)]
            self.gui.request('set_world_control_buttons', world_controls)
        else:
            self.gui.request('set_world_control_buttons', [])

        self.refresh_draft_gui()

    def refresh_draft_gui(self):
        self.refresh_draftables()
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
                sprite = Assets.get_sprite('ui.blank')
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

        if self.encounter_api is None:
            draft_control = SpriteLabel(ep.sprite, f'Play encounter', None)
        else:
            s = self.encounter_api.encounter_params.sprite
            draft_control = SpriteLabel(s, f'Encounter in progress!', None)
        self.gui.request('set_draft_control_buttons', [
            draft_control,
            SpriteLabel(Assets.get_sprite('abilities.vzero'), f'Return to world', None),
        ])

    def refresh_draftables(self):
        debug = PROFILE.get_setting('misc.debug_mode') and DEV_BUILD  # Allow draft all
        self.draftables = []
        for aid in AID_LIST:
            if ABILITIES[aid].draftable or debug:
                self.draftables.append(aid)

    @property
    def world_label(self):
        return '\n'.join([
            f'Victory Points: {self.victory_points}',
            f'Silver bank: {self.silver_bank}',
            '',
            f'Metagame Balance: {METAGAME_BALANCE_SHORT}',
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

    def handle_world_control_button(self, event):
        if event.index == 0:
            Assets.play_sfx('ui.select', volume='ui')
            self.gui.request('switch_screen', 'encounter')
        else:
            Assets.play_sfx('ui.target', volume='ui')
            logger.warning(f'Unknown world control index: {event}')

    def handle_world_stack_activate(self, event):
        Assets.play_sfx('ui.select', volume='ui')
        self.selected_encounter = event.index
        self.refresh_draft_gui()
        self.gui.request('set_view', 'draft')

    def handle_world_stack_select(self, event):
        self.handle_world_stack_inspect(event)

    def handle_world_stack_inspect(self, event):
        ep = self.world_encounters[event.index]
        self.gui.request('activate_tooltip', SpriteTitleLabel(ep.sprite, ep.map, ep.description, None))

    def handle_draft_activate(self, event):
        self.draft(self.draftables[event.index])

    def handle_draft_select(self, event):
        self.handle_draft_inspect(event)

    def handle_draft_inspect(self, event):
        aid = self.draftables[event.index]
        ability = ABILITIES[aid]
        # ability.play_sfx(volume='ui')
        self.gui.request('activate_tooltip', SpriteTitleLabel(
            ability.sprite,
            f'{ability.name}\nDraft cost: {ability.draft_cost}',
            ability.universal_description,
            (0,0,0,0)))

    def handle_draft_control_button(self, event):
        Assets.play_sfx('ui.select', volume='ui')
        if event.index == 0:
            if self.encounter_api is not None:
                self.gui.request('switch_screen', 'encounter')
            else:
                self.new_encounter()
        elif event.index == 1:
            self.gui.request('set_view', 'world')

    def handle_loadout_activate(self, event):
        aid = self.loadout[event.index]
        if aid is not None:
            self.draft(aid)

    def handle_loadout_select(self, event):
        # self.handle_loadout_inspect(event)
        pass

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
            Assets.play_sfx('ui.select', volume='ui')
            self.refresh_draft_gui()
