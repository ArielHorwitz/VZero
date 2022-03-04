import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np
from collections import defaultdict

from nutil.vars import nsign, nsign_str, modify_color, is_iterable, minmax, NP, PublishSubscribe
from nutil.random import SEED, h256
from nutil.display import njoin, make_title
from nutil.time import RateCounter, ping, pong, humanize_ms
from nutil.file import file_load

from data import VERSION
from data.load import RDF
from data.settings import PROFILE, DEV_BUILD
from data.assets import Assets
from gui.api import SpriteTitleLabel, ProgressBar, SpriteBox, SpriteLabel
from gui.api import ControlEvent, InputEvent, CastEvent

from logic.common import *

from logic import MECHANICS_NAMES
from logic.abilities import ABILITIES
from logic.engine import Engine as EncounterEngine
from logic.mechanics import Mechanics
from logic.mapgen import MapGenerator, MAP_DATA
from logic.items import ITEM, ITEMS, ITEM_CATEGORIES, Item


metagame_data = str(VERSION) + str(DEV_BUILD) + ''.join(str(RDF.from_file(RDF.CONFIG_DIR / f'{_}.rdf').raw_dict) for _ in (
    'abilities', 'items', 'units',
)) + str(MAP_DATA)
METAGAME_BALANCE = h256(metagame_data)
METAGAME_BALANCE_SHORT = METAGAME_BALANCE[:4].upper()
logger.info(f'Metagame Balance: {METAGAME_BALANCE_SHORT} ({METAGAME_BALANCE})')



DIFFICULTY_LEVELS = ['Sandbox', 'Easy mode', 'Medium challenge', 'Hard difficulty', 'Impossible...']
DIFFICULTY2STOCKS = {
    0: 100,
    1: 10,
    2: 5,
    3: 3,
    4: 1,
}

FEEDBACK_SFX = {
    'shop': 'ui.shop',
    'select': 'ui.select',
    'ouch': 'ui.ouch',
    'ouch2': 'ui.ouch2',
    FAIL_RESULT.INACTIVE: 'ui.target',
    FAIL_RESULT.MISSING_TARGET: 'ui.target',
    FAIL_RESULT.OUT_OF_BOUNDS: 'ui.target',
    FAIL_RESULT.OUT_OF_ORDER: 'ui.target',
    FAIL_RESULT.OUT_OF_RANGE: 'ui.range',
    FAIL_RESULT.ON_COOLDOWN: 'ui.cooldown',
    FAIL_RESULT.MISSING_COST: 'ui.cost',
}


SELECTION_SPRITE = Assets.get_sprite('ui.crosshair-select')
QUICKCAST_SPRITE = Assets.get_sprite('ui.crosshair-cast')

ENEMY_COLOR = (1, 0, 0, 1)
ALLY_COLOR = (0, 0.7, 0, 1)
NEUTRAL_COLOR = (0.8, 0.5, 0.2, 1)
MANA_COLOR = (0, 0.25, 1, 1)

STAT_SPRITES = tuple([Assets.get_sprite(s) for s in (
    'mechanics.physical', 'mechanics.fire', 'mechanics.earth',
    'mechanics.air', 'mechanics.water', 'mechanics.gold',
    'mechanics.respawn', 'ui.crosshair-select', 'ui.distance'
)])
HUD_STATUSES = {str2stat(s): str2status(s) for s in MECHANICS_NAMES if s is not 'SHOP'}

SHOP_STATE_KEY = defaultdict(lambda: 0.7, {
    True: 1,
    FAIL_RESULT.MISSING_COST: 0.45,
    FAIL_RESULT.MISSING_TARGET: 0.2,
    FAIL_RESULT.OUT_OF_RANGE: 1,
    FAIL_RESULT.ON_COOLDOWN: 0,
})
SHOP_MAIN_TEXT = '\n'.join([
    '[u]Legend:[/u]',
    'White: for sale',
    'Grey: missing gold/slots',
    'Black: already owned',
    'Color: for sale at another shop',
    '',
    '[u]Refund policy:[/u]',
    '80% refund on used items',
    '100% refund on new items (<10 seconds)',
])
SHOP_MAIN_TEXT_NOSHOP = '\n'.join([
    f'Press {PROFILE.get_setting("hotkeys.toggle_map")} to find a shop',
    *(f'{_+1}. {n.name.lower().capitalize()} shop' for _, n in enumerate(ITEM_CATEGORIES)),
])


class EncounterAPI:
    enc_over = False
    win = False
    player_uid = 0
    selected_unit = 0
    map_mode = False
    view_offset = None
    view_size = gui_size = np.array([1024, 768])

    def __init__(self, game, encounter_params, player_abilities):
        self.debug_mode = False
        self.settings_notifier = PublishSubscribe(name='ELogic')

        # Logic related properties
        self.game = game
        self.encounter_params = encounter_params
        self.difficulty_level = encounter_params.difficulty
        self.engine = EncounterEngine(self)
        self.map = MapGenerator(self, encounter_params)
        self.player = self.units[self.player_uid]
        self.player.set_abilities(player_abilities)
        self.always_visible = np.zeros(len(self.engine.units), dtype=np.bool)
        self.always_active = np.zeros(len(self.engine.units), dtype=np.bool)

        # GUI related properties
        self.__last_hud_statuses = []
        self.__last_fail_sfx_ping = ping()
        self.map_mode = False
        self.default_upp = 2

        # Settings
        self.settings_notifier.subscribe('audio.feedback_sfx_cooldown', self.setting_feedback_sfx_interval)
        self.setting_feedback_sfx_interval()
        self.settings_notifier.subscribe('misc.log_interval', self.setting_log_interval)
        self.settings_notifier.subscribe('misc.auto_log', self.setting_log_interval)
        self.setting_log_interval()
        hotkeys = self.setting_hotkeys()
        for hk in hotkeys:
            self.settings_notifier.subscribe(hk, self.setting_hotkeys)

        # Setup units
        self.engine.set_stats(self.player_uid, STAT.STOCKS, DIFFICULTY2STOCKS[self.difficulty_level])
        for unit in self.engine.units:
            unit.action_phase()
            self.always_visible[unit.uid] = unit.always_visible
            self.always_active[unit.uid] = unit.always_active

    def setting_feedback_sfx_interval(self):
        self.__feedback_sfx_interval = PROFILE.get_setting('audio.feedback_sfx_cooldown')

    def setting_log_interval(self):
        self.__log_interval_ticks = PROFILE.get_setting('misc.log_interval')
        self.__last_log_interval = self.engine.tick - (self.__log_interval_ticks + 1)

    def setup(self, interface):
        self.gui = interface
        self.settings_notifier.subscribe('ui.detailed_mode', self.setting_detailed_mode)
        self.setting_detailed_mode()
        logger.info(f'Encounter setup received interface: {interface}')
        self.map.setup(self.gui)
        self.set_widgets()
        self.set_zoom()
        self.settings_notifier.subscribe('misc.debug_mode', self.setting_debug_mode)
        self.setting_debug_mode()

    def setting_hotkeys(self):
        self.hud_left_hotkeys = []
        self.hud_right_hotkeys = []
        hotkeys = set()
        for i in range(8):
            for ktype, l in (('ability', self.hud_left_hotkeys), ('item', self.hud_right_hotkeys)):
                key_name = f'hotkeys.{ktype}_{i+1}'
                key = PROFILE.get_setting(key_name)
                hotkeys.add(key_name)
                l.append(str(key).upper())
        return hotkeys

    def update(self):
        with self.engine.total_timers['logic_total'].time_block:
            self.gui_size = self.gui.request('get_gui_size')
            self.view_size = self.gui_size * self.upp

            if not self.enc_over:
                player_action_radius = min(self.units[0].view_distance+1000, 3000)
                in_action_radius = self.engine.get_distances(self.engine.get_position(0)) < player_action_radius
                active_uids = self.always_active | in_action_radius
                self.engine.update(active_uids)
                if self.__last_log_interval + self.__log_interval_ticks < self.engine.tick:
                    self.log_player_state()
                    self.__last_log_interval = self.engine.tick

            with self.engine.total_timers['logic_gui_refresh'].time_block:
                self.refresh_gui()

            # Handle GUI event queue
            with self.engine.total_timers['handle_events'].time_block:
                for event in self.gui.get_flush_queue():
                    self._handle_event(event)

    def set_widgets(self):
        sprites = [unit.sprite for unit in self.units]
        hp_bar_colors = [self.relative_allegiance_color(self.player_uid, uid) for uid in range(self.unit_count)]
        mana_bar_colors = [MANA_COLOR for _ in range(self.unit_count)]
        self.gui.request('set_units', sprites, hp_bar_colors, mana_bar_colors)
        self.gui.request('set_move_crosshair', self.engine.get_position(self.player_uid, value_name=VALUE.TARGET), (50, 50))
        self.gui.request('set_top_panel_color', self.top_panel_color)
        self.gui.request('set_browse_main', self.browse_main())
        self.gui.request('set_browse_elements', self.browse_elements())
        self.gui.request('set_menu_text', self.menu_text)
        self.gui.request('set_menu_leave_text', 'Give up', 'Ditch encounter?')

    def refresh_gui(self):
        self.gui.request('set_view_center', self.view_center)
        self.gui.request('set_move_crosshair', self.engine.get_position(self.player_uid, value_name=VALUE.TARGET))
        with self.engine.total_timers['gui_vfx'].time_block:
            self.gui.request('set_vfx', self.engine.get_visual_effects())
        self.refresh_gui_sprite_layer()
        self.refresh_hud()
        self.refresh_shop()
        self.refresh_debug()

    def refresh_gui_sprite_layer(self):
        with self.engine.total_timers['gui_sprite_layer'].time_block:
            self.gui.request('set_view_fade', 0 if self.engine.auto_tick else 0.5)
            self.gui.request('set_top_panel_labels', *self.top_panel_labels)
            self.gui.request('set_fog_center', self.player.position)
            self.gui.request('set_fog_radius', self.player.view_distance + Mechanics.get_stats(self.engine, self.player_uid, STAT.HITBOX))
            visible_mask = self.sprite_visible_mask
            radii = Mechanics.get_stats(self.engine, visible_mask, STAT.HITBOX)
            positions = self.engine.get_positions(visible_mask)
            top_bars, bot_bars = self.sprite_bars(visible_mask)
            with self.engine.total_timers['gui_sprite_statuses'].time_block:
                statuses = [self.sprite_statuses(uid) for uid in np.flatnonzero(visible_mask)]
            self.gui.request('update_units', visible_mask, radii, positions, top_bars, bot_bars, statuses)

    def refresh_hud(self):
        with self.engine.total_timers['gui_hud'].time_block:
            unit = self.units[self.selected_unit]
            self.gui.request('set_huds', self.hud_left(), self.hud_middle(), self.hud_right(), self.hud_statuses())
            self.gui.request('set_hud_bars', *self.hud_bars())
            self.gui.request('set_hud_portrait', unit.sprite, unit.name)
            self.gui.request('set_hud_middle_label', unit.say)

    def refresh_shop(self):
        with self.engine.total_timers['gui_shop'].time_block:
            if not self.gui.request('browse_showing'):
                return
            self.gui.request('set_browse_main', self.browse_main())
            self.gui.request('set_browse_elements', self.browse_elements())

    def refresh_debug(self):
        if self.debug_mode:  # Refresh debug panels
            with self.engine.total_timers['gui_debug_panels'].time_block:
                self.gui.request('set_debug_panels', self.debug_panel_labels())

    def leave(self):
        self.enc_over = True
        return self.win, self.encounter_params

    def end_encounter(self, win):
        self.enc_over = True
        self.win = win
        self.gui.request('set_menu_leave_text', 'Return to world', 'Let\'s get outta here...')
        Assets.play_sfx('ui.win' if win else 'ui.lose', volume='feedback')
        logger.info(f'Encounter over! Win: {self.win}')
        self.toggle_play(set_to=False)
        self.gui.request('set_menu_text', self.menu_text)
        self.gui.request('menu_show')

    # Utilities
    def select_unit(self, uid):
        self.selected_unit = uid
        logger.info(f'Selected unit: {self.units[uid].name}')
        for stat, tracker in self.units[uid].regen_trackers.items():
            tracker.reset(self.engine.get_delta_total(uid, stat))

    @property
    def units(self):
        return self.engine.units

    def map_select(self, target):
        play_sfx = False
        distances = self.engine.get_distances(target)
        uid = NP.argmin(distances, self.sprite_visible_mask)
        dist = distances[uid]
        if dist < 50 * self.upp:
            play_sfx = True
        else:
            uid = 0
        self.select_unit(uid)
        self.draw_unit_selection(uid, play_sfx=play_sfx)

    def draw_unit_selection(self, uid, play_sfx=False):
        if play_sfx:
            Assets.play_sfx('ui.select', volume='feedback')
        hb = self.engine.get_stats(uid, STAT.HITBOX)
        self.engine.add_visual_effect(VFX.SPRITE, 60, {
            'uid': uid,
            'fade': 100,
            'source': SELECTION_SPRITE,
            'size': (hb*2.1, hb*2.1),
            'color': (0, 0, 0),
        })

    def toggle_play(self, set_to=None, play_sfx=True):
        set_to = set_to if set_to is not None else not self.engine.auto_tick
        changed = set_to != self.engine.auto_tick
        self.engine.set_auto_tick(set_to)
        logger.debug(f'ELogic toggled play')
        if play_sfx and changed:
            if self.engine.auto_tick is True:
                Assets.play_sfx('ui.play', volume='ui')
            else:
                Assets.play_sfx('ui.pause', volume='ui')

    @property
    def map_size(self):
        return self.map.size

    def hp_zero(self, uid):
        self.engine.units[uid].hp_zero()

    def status_zero(self, uid, status):
        unit = self.engine.units[uid]
        status = list(STATUS)[status]
        self.engine.units[uid].status_zero(status)

    sfx_feedback_uids = miss_feedback_uids = {0}  # Assuming player is created first
    def play_feedback(self, feedback, uid=0):
        if not uid in self.sfx_feedback_uids:
            return
        if pong(self.__last_fail_sfx_ping) > self.__feedback_sfx_interval:
            if feedback in FEEDBACK_SFX:
                Assets.play_sfx(FEEDBACK_SFX[feedback], volume='feedback')
                self.__last_fail_sfx_ping = ping()

    ouch_feedback_uids = {0, 1}  # Assuming player then fort are created first
    def ouch(self, uids):
        if not (set(uids) & self.ouch_feedback_uids):
            return
        sfx, color = ('ouch', COLOR.RED) if 0 in uids else ('ouch2', COLOR.BLUE)

        Assets.play_sfx(f'ui.{sfx}', volume='feedback')
        self.engine.add_visual_effect(VFX.BACKGROUND, 60, params={
            'color': modify_color(color, a=0.3),
            'fade': 60,
        })

    def relative_allegiance_color(self, observing_uid, target_uid):
        obs_allegiance = self.units[observing_uid].allegiance
        target_allegiance = self.units[target_uid].allegiance
        if obs_allegiance == target_allegiance:
            return ALLY_COLOR
        hostile = target_allegiance > 0
        return ENEMY_COLOR if hostile else NEUTRAL_COLOR

    # GUI utilities
    @property
    def upp(self):
        return self.fit_upp(self.map_size * 1.1) if self.map_mode else self.default_upp

    @property
    def view_center(self):
        if self.map_mode:
            return self.map_size / 2
        return self.engine.get_position(0) if self.view_offset is None else self.view_offset

    def toggle_map(self):
        self.map_mode = not self.map_mode
        self.view_offset = None
        self.gui.request('set_view_center', self.view_center)
        self.gui.request('set_upp', self.upp)

    def toggle_shop(self):
        self.selected_unit = 0
        showing = self.gui.request('browse_showing')
        if PROFILE.get_setting('ui.auto_pause_shop'):
            self.toggle_play(set_to=showing)
        self.gui.request('browse_hide' if showing else 'browse_show')

    def set_zoom(self, d=None, v=None):
        if v is not None:
            self.default_upp = v
            return
        if d is None:
            self.default_upp = 1 / (PROFILE.get_setting('ui.default_zoom')/100)
        else:
            self.default_upp *= abs(d)**(-1*nsign(d))
        self.default_upp = minmax(
            self.fit_upp(self.engine.get_stats(self.player_uid, STAT.HITBOX)),
            self.fit_upp(self.map_size * 0.9),
            self.default_upp
        )
        self.gui.request('set_upp', self.upp)

    def fit_upp(self, real_size):
        return max(np.array(real_size) / self.gui_size)

    def zoom_in(self):
        if not self.map_mode:
            self.set_zoom(d=1.15)

    def zoom_out(self):
        if not self.map_mode:
            self.set_zoom(d=-1.15)

    def pan(self, d, a=None):
        if a is None:
            a = min(self.view_size) * 0.15
        if self.view_offset is None:
            self.view_offset = self.view_center
        hoff = (d=='right') - (d=='left')
        voff = (d=='up') - (d=='down')
        offset = np.array([a*hoff, a*voff])
        self.view_offset += offset

    def setting_debug_mode(self):
        debug_mode_setting = PROFILE.get_setting('misc.debug_mode')
        self.debug_mode = debug_mode_setting and DEV_BUILD
        logger.info(f'Toggle debug_mode, now: {self.debug_mode} (debug:{debug_mode_setting} dev_build:{DEV_BUILD})')
        self.gui.request('debug_show' if self.debug_mode else 'debug_hide')  # Toggle debug panels

    def setting_detailed_mode(self):
        self.detailed_info_mode = PROFILE.get_setting('ui.detailed_mode')
        if not self.detailed_info_mode:
            self.gui.request('deactivate_tooltip')
    # GUI elements
    @property
    def time_str(self):
        return humanize_ms(self.engine.ticktime * self.engine.tick, show_hours=False)

    @property
    def menu_text(self):
        if self.enc_over:
            difficulty = DIFFICULTY_LEVELS[self.difficulty_level]
            if self.win:
                return '\n'.join([
                    f'[b][u]You win![/u][/b]',
                    difficulty,
                    f'Draft cost: {self.units[0].draft_cost}',
                    f'Time: {self.time_str}',
                    f'Stocks: {self.units[0].stocks}',
                ])
            else:
                return f'You lose :(\n{difficulty}\nBetter luck next time!'
        return f'[b]Paused[/b]'

    @property
    def top_panel_labels(self):
        mouse_pos = tuple(round(_) for _ in self.gui.request("get_mouse_pos"))
        bstr = f'DEV BUILD {mouse_pos}' if DEV_BUILD else f'Balance patch: {METAGAME_BALANCE_SHORT}'
        if self.debug_mode:  # Top panel label
            dstr = " / ".join(str(round(_, 1)) for _ in self.engine.get_position(0)/100)
        else:
            d = DIFFICULTY_LEVELS[self.difficulty_level].split(' ', 1)[0].lower()
            dstr = f'{self.units[0].networth_str} ({d})'
        paused_str = '' if self.engine.auto_tick else 'Paused'
        view_size = '×'.join(str(round(_)) for _ in np.array(self.gui_size) * self.upp)
        vstr = f'{view_size} ({round(100 / self.upp)}% zoom)'
        return [
            bstr,
            dstr,
            f'{paused_str}\n{self.time_str}',
            vstr,
        ]

    @property
    def top_panel_color(self):
        if DEV_BUILD:  # TOP PANEL COLOR
            return 0, 0.5, 1, 1
        return 1, 1, 1, 1

    @property
    def sprite_visible_mask(self):
        if self.debug_mode and self.detailed_info_mode:  # Player view distance
            max_los = float('inf')
        else:
            max_los = self.player.view_distance
        in_los = self.engine.unit_distance(self.player_uid) <= max_los
        is_ally = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) == self.engine.get_stats(self.player_uid, STAT.ALLEGIANCE)
        return in_los | is_ally | self.always_visible

    def sprite_bars(self, mask):
        max_hps = self.engine.get_stats(mask, STAT.HP, value_name=VALUE.MAX)
        hps = self.engine.get_stats(mask, STAT.HP) / max_hps
        max_manas = self.engine.get_stats(mask, STAT.MANA, value_name=VALUE.MAX)
        manas = self.engine.get_stats(mask, STAT.MANA) / max_manas
        manas[hps<=0] = 0
        return hps, manas

    def sprite_statuses(self, uid):
        icons = []
        respawn = self.engine.get_status(uid, STATUS.RESPAWN)
        if respawn > 0:
            duration = self.engine.get_status(uid, STATUS.RESPAWN, STATUS_VALUE.DURATION)
            icons.append(Assets.get_sprite('mechanics.respawn'))

        if self.engine.get_status(uid, STATUS.FOUNTAIN) > 0:
            icons.append(Assets.get_sprite('units.fort'))

        shop = self.engine.get_status(uid, STATUS.SHOP)
        if shop > 0:
            shop = list(ITEM_CATEGORIES)[round(shop)-1].name.lower().capitalize()
            icons.append(Assets.get_sprite('units.basic-shop'))

        for status in HUD_STATUSES.values():
            d = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
            if d > 0:
                name = status.name.lower().capitalize()
                icons.append(Assets.get_sprite(f'mechanics.{name}'))

        return icons

    def hud_left(self):
        uid = self.selected_unit
        sls = []
        for i, aid in enumerate(self.units[uid].ability_slots):
            if aid is None:
                sls.append(SpriteBox(str(Assets.get_sprite('ui.blank')), f'\n{self.hud_left_hotkeys[i]}' if self.detailed_info_mode else '', (0,0,0,0), (1,1,1,1)))
                continue
            ability = self.abilities[aid]
            s, color = ability.gui_state(self.engine, uid)
            if self.detailed_info_mode:
                s = f'{s}\n{self.hud_left_hotkeys[i]}'
            sls.append(SpriteBox(ability.sprite, s, modify_color(color, a=1), (1,1,1,1)))
        return sls

    def hud_right(self):
        uid = self.selected_unit
        sls = []
        for i, iid in enumerate(self.units[uid].item_slots):
            if iid is None:
                sls.append(SpriteBox(Assets.get_sprite('ui.blank'), f'\n{self.hud_right_hotkeys[i]}' if self.detailed_info_mode else '', (0,0,0,0), (1,1,1,1)))
                continue
            item = ITEMS[iid]
            s, color = item.gui_state(self.engine, uid)
            if self.detailed_info_mode:
                s = f'{s}\n{self.hud_right_hotkeys[i]}'
            sls.append(SpriteBox(item.sprite, s, modify_color(color, a=1), (1,1,1,1)))
        return sls

    def hud_middle_label(self):
        return self.units[self.selected_unit].say

    def hud_middle(self):
        uid = self.selected_unit

        current = self.engine.get_stats(uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
            STAT.AIR, STAT.WATER, STAT.GOLD,
        ])
        gold = current[-1]
        current = [f'{math.floor(c)}' for c in current]
        current.extend([
            f'{round(self.units[uid]._respawn_timer/100)}s',
            f'{round(self.engine.get_stats(uid, STAT.HITBOX))}',
            f'{round(self.engine.unit_distance(0, uid))}',
        ])
        return tuple(SpriteLabel(
            STAT_SPRITES[i], current[i],
            None) for i in range(9))

    def hud_statuses(self):
        def format_time(t):
            return math.ceil(ticks2s(t))

        uid = self.selected_unit
        self.__last_hud_statuses = []
        strs = []
        respawn = self.engine.get_status(uid, STATUS.RESPAWN)
        if respawn > 0:
            duration = self.engine.get_status(uid, STATUS.RESPAWN, STATUS_VALUE.DURATION)
            strs.append(SpriteBox(
                Assets.get_sprite('mechanics.respawn'),
                f'\n{format_time(duration)}s',
                (0,0,0,0), (0,0,0,0),
            ))
            self.__last_hud_statuses.append(STATUS.RESPAWN)

        if self.engine.get_status(uid, STATUS.FOUNTAIN) > 0:
            strs.append(SpriteBox(
                Assets.get_sprite('units.fort'), '',
                (0,0,0,0), (0,0,0,0),
            ))
            self.__last_hud_statuses.append('fountain')

        shop_status = Mechanics.get_status(self.engine, uid, STAT.SHOP)
        shop_name, shop_color = Item.item_category_gui(shop_status)
        if shop_name is not None:
            strs.append(SpriteBox(
                Assets.get_sprite(f'units.{shop_name}-shop'), '',
                (0,0,0,0), (0,0,0,0),
            ))
            self.__last_hud_statuses.append(STATUS.SHOP)

        for stat, status in HUD_STATUSES.items():
            v = Mechanics.get_status(self.engine, uid, stat)
            if v > 0:
                name = stat.name.lower().capitalize()
                duration = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
                ds = f'* {format_time(duration)}s' if duration > 0 else ''
                strs.append(SpriteBox(
                    Assets.get_sprite(f'mechanics.{name}'), f'{ds}\n{round(v)}',
                    (0,0,0,0), (0,0,0,0),
                ))
                self.__last_hud_statuses.append(stat)

        return strs

    def hud_bars(self):
        uid = self.selected_unit
        unit = self.units[uid]
        hp = self.engine.get_stats(uid, STAT.HP)
        mana = self.engine.get_stats(uid, STAT.MANA)
        max_hp = self.engine.get_stats(uid, STAT.HP, value_name=VALUE.MAX)
        max_mana = self.engine.get_stats(uid, STAT.MANA, value_name=VALUE.MAX)
        unit.regen_trackers[STAT.HP].push(self.engine.get_delta_total(uid, STAT.HP))
        unit.regen_trackers[STAT.MANA].push(self.engine.get_delta_total(uid, STAT.MANA))
        delta_hp = f'{nsign_str(round(s2ticks(unit.regen_trackers[STAT.HP].mean), 1))} /s'
        delta_mana = f'{nsign_str(round(s2ticks(unit.regen_trackers[STAT.MANA].mean), 1))} /s'
        return [
            ProgressBar(hp/max_hp, f'HP: {hp:.1f}/{max_hp:.1f} {delta_hp}', self.relative_allegiance_color(self.player_uid, uid)),
            ProgressBar(mana/max_mana, f'Mana: {mana:.1f}/{max_mana:.1f} {delta_mana}', MANA_COLOR),
        ]

    def browse_main(self):
        shop_status = Mechanics.get_status(self.engine, 0, STAT.SHOP)
        shop_name, shop_color = Item.item_category_gui(shop_status)
        if shop_name is not None:
            title = f'{shop_name.capitalize()} Shop'
            gold_count = int(self.engine.get_stats(0, STAT.GOLD))
            warning = ''
            if self.units[0].empty_item_slots == 0:
                shop_color = (0,0,0,1)
                warning = 'Missing slots!'
            main_text = '\n'.join([
                f'You have: [b]{gold_count}[/b] gold',
                f'[u][b]{warning}[/b][/u]',
                f'',
                SHOP_MAIN_TEXT,
            ])
        else:
            title = 'Out of shop range'
            shop_color = (0.25,0.25,0.25,1)
            main_text = SHOP_MAIN_TEXT_NOSHOP
        return SpriteTitleLabel(
            Assets.get_sprite(f'units.{shop_name}-shop'),
            title, main_text,
            modify_color(shop_color, v=0.5)
        )

    def browse_elements(self):
        sts = []
        for item in ITEMS:
            s = str(round(item.cost))
            r = item.check_buy(self.engine, 0)
            near_shop = r is not FAIL_RESULT.OUT_OF_RANGE
            already_owned = r is FAIL_RESULT.ON_COOLDOWN
            shop_color = (1,1,1) if (near_shop or already_owned) else item.color
            bg_color = modify_color(shop_color, v=SHOP_STATE_KEY[r])
            sts.append(SpriteBox(
                item.sprite,
                s, bg_color, None))
        return sts

    # Misc
    abilities = ABILITIES
    items = ITEMS
    ItemCls = Item

    def log_player_state(self, force=False):
        if PROFILE.get_setting('misc.auto_log') or force:
            logger.info('\n'.join([
                '\n\n\n',
                f'__ PLAYER STATE __',
                f'Tick: {self.engine.tick} Active UIDs: {np.flatnonzero(self.engine.active_uids)}',
                f'__ STATS __',
                self.pretty_stats(self.player_uid, verbose=True),
                f'__ STATUSES __',
                self.pretty_statuses(self.player_uid, verbose=True),
                f'__ COOLDOWNS __',
                self.pretty_cooldowns(self.player_uid, verbose=True),
                f'__ UNIT DEBUG_STR __',
                self.player.debug_str(verbose=True),
            ]))

    @property
    def unit_count(self):
        return len(self.units)

    def pretty_stats(self, uid, stats=None, verbose=False):
        unit = self.units[uid]
        if stats is None:
            stats = STAT
        stat_table = self.engine.stats.table
        target = self.engine.get_position(uid, value_name=VALUE.TARGET)
        s = [
            f'Target XY: {tuple(round(_, 3) for _ in target)}',
        ]
        for stat in stats:
            current = stat_table[uid, stat, VALUE.CURRENT]
            delta = s2ticks()*stat_table[uid, stat, VALUE.DELTA]
            d_str = f' + {delta:.3f}' if delta != 0 else ''
            max_value = stat_table[uid, stat, VALUE.MAX]
            mv_str = f' / {max_value:.3f}' if max_value < 100_000 else ''
            s.append(f'{stat.name.lower().capitalize()}: {current:3.3f}{d_str}{mv_str}')
        return njoin(s)

    def pretty_statuses(self, uid, verbose=False):
        t = []
        for status in STATUS:
            d = self.engine.get_status(uid, status, value_name=STATUS_VALUE.DURATION)
            s = self.engine.get_status(uid, status, value_name=STATUS_VALUE.STACKS)
            if d > 0 or verbose:
                name_ = status.name.lower().capitalize()
                t.append(f'{name_}: {s:.3f} × {round(ticks2s(d), 2)}')
        return njoin(t) if len(t) > 0 else 'No statuses'

    def pretty_cooldowns(self, uid, verbose=False):
        unit = self.units[uid]
        s = []
        for aid in unit.abilities | unit.item_abilities:
            v = self.engine.get_cooldown(uid, aid)
            if v > 0 or ABILITIES[aid].debug or verbose:
                name_ = aid.name.lower().capitalize()
                s.append(f'{name_}: {ticks2s(v):.2f} ({v:.1f})')
        return njoin(s) if len(s) > 0 else f'No cooldowns'

    def debug_panel_labels(self):
        def display_timer_collection(collection):
            strs = []
            for tname, timer in collection.items():
                if isinstance(timer, RateCounter):
                    m = timer.mean_elapsed_ms
                    if m > 0.5:
                        strs.append(f'[b]{tname}: {m:.3f} ms[/b]')
                    else:
                        strs.append(f'{tname}: {m:.3f} ms')
            return '\n'.join(strs)

        verbose = True
        logic_performance = '\n'.join([
            make_title('Logic Performance Totals', length=30),
            display_timer_collection(self.engine.total_timers),
            make_title('Single', length=30),
            display_timer_collection(self.engine.single_timers),
        ])

        if not self.detailed_info_mode:
            return [logic_performance]

        logic_overview = njoin([
            make_title(f'Logic Overview', length=30),
            f'Game time: {self.time_str}',
            f'Tick: {self.engine.tick} +{TPS} t/s',
            f'Map size: {self.map_size}',
            f'Agency phase: {self.engine.tick % self.engine.AGENCY_PHASE_COUNT}',
            make_title(f'Stats Engine Debug', length=30),
            f'{self.engine.stats.debug_str(verbose=verbose)}',
        ])

        uid = self.selected_unit
        unit = self.engine.units[uid]
        text_unit1 = '\n'.join([
            make_title(f'{unit.name} (#{unit.uid}) debug', length=30),
            f'\n{unit.debug_str(verbose=verbose)}',
        ])
        text_unit2 = '\n'.join([
            make_title(f'Stats', length=30),
            f'{self.pretty_stats(uid, verbose=verbose)}',
            make_title(f'Statuses', length=30),
            f'{self.pretty_statuses(uid, verbose=verbose)}',
        ])
        text_unit3 = '\n'.join([
            make_title(f'Abilities', length=30),
            *(repr(_) for _ in unit.ability_slots),
            make_title(f'Items', length=30),
            *(repr(_) for _ in unit.item_slots),
            make_title(f'Unslotted', length=30),
            *(repr(_) for _ in unit.unslotted_abilities),
            make_title(f'Cooldown', length=30),
            f'{self.pretty_cooldowns(uid, verbose=verbose)}',
        ])

        return logic_performance, logic_overview, text_unit1, text_unit2, text_unit3

    def debug_pointer(self, pos, **params):
        self.engine.add_visual_effect(VFX.SPRITE, 50, {
            'source': QUICKCAST_SPRITE,
            'point': pos,
            'size': (250, 250),
            'color': (0, 0, 0, 1),
            **params,
        })

    # GUI event handlers
    def _handle_event(self, event):
        logger.debug(f'ELogic handling event: {event}')
        if self.gui.request('menu_showing') and event.name != 'toggle_menu':
            self.play_feedback(FAIL_RESULT.INACTIVE)
            return
        if isinstance(event, CastEvent):
            self.__handle_cast(event)
            return
        if isinstance(event, InputEvent):
            handler_name = f'_ihandle_{event.name}'
            if not hasattr(self, handler_name):
                logger.warning(f'ELogic missing input handler for: {event.name}. Event: {event}')
                return
            handler = getattr(self, handler_name)
            handler(event)
            return
        if isinstance(event, ControlEvent):
            if event.name.startswith('dev'):
                self.__handle_dev(event)
                return
            elif event.name.startswith('pan'):
                self.__handle_pan(event)
            handler_name = f'_chandle_{event.name}'
            if not hasattr(self, handler_name):
                logger.warning(f'ELogic missing control handler for: {event.name}. Event: {event}')
                return
            handler = getattr(self, handler_name)
            handler(event)
            return
        logger.warning(f'Unknown event type: {event}')
        return

    def __handle_cast(self, event):
        if event.name == 'ability':
            self.units[0].use_ability_slot(event.index, event.pos, event.alt)
        elif event.name == 'item':
            self.units[0].use_item_slot(event.index, event.pos, event.alt)
        else:
            logger.warning(f'Unknown cast type: {event.name} (from event: {event})')

    def __handle_pan(self, event):
        self.pan(d=event.name[4:])

    def __handle_dev(self, event):
        if not DEV_BUILD:  # HANDLE DEV ACTION
            return
        if event.name == 'dev1':
            logger.info(f'Dev doing 1 tick...')
            self.engine._do_ticks(1)
        elif event.name == 'dev2':
            logger.info(f'Dev doing 3000 ticks...')
            self.engine._do_ticks(3000)
        elif event.name == 'dev3':
            gdelta = self.engine.get_position(self.player_uid) == self.player.grave_pos
            if gdelta.sum() == 2:
                logger.info(f'Dev returning from graveyard...')
                self.player.move_to_spawn()
            else:
                logger.info(f'Dev moving to graveyard...')
                self.player.move_to_graveyard()

    # GUI input event handlers
    def _ihandle_activate(self, event):
        self.player.use_walk(event.pos)

    def _ihandle_select(self, event):
        self.map_select(event.pos)

    def _ihandle_loot(self, event):
        self.player.use_loot(event.pos)

    def _ihandle_zoomin(self, event):
        self.zoom_in()

    def _ihandle_zoomout(self, event):
        self.zoom_out()

    def _ihandle_inspect(self, event):
        self.view_offset = event.pos

    def _ihandle_back(self, event):
        self.map_mode = False
        self.view_offset = None
        self.set_zoom()

    def _ihandle_forward(self, event):
        self.map_mode = not self.map_mode
        self.view_offset = None

    # GUI control event handlers
    def _chandle_toggle_play(self, event):
        self.toggle_play()

    def _chandle_toggle_menu(self, event):
        showing_menu = self.gui.request('menu_showing')
        self.toggle_play(set_to=showing_menu)
        self.gui.request('menu_hide' if showing_menu else 'menu_show')
        self.gui.request('browse_hide')

    def _chandle_toggle_map(self, event):
        self.toggle_map()

    def _chandle_toggle_shop(self, event):
        self.toggle_shop()

    def _chandle_reset_view(self, event):
        self.map_mode = False
        self.view_offset = None
        self.set_zoom()
        self.gui.request('set_upp', self.upp)

    def _chandle_unpan(self, event):
        self.view_offset = None
        self.map_mode = False
        self.gui.request('set_upp', self.upp)

    def _chandle_zoom_in(self, event):
        self.zoom_in()

    def _chandle_zoom_out(self, event):
        self.zoom_out()

    def _chandle_left_hud_drag_drop(self, event):
        origin, target = event.index
        if self.selected_unit == self.player_uid and origin != target:
            self.player.swap_ability_slots(origin, target)
            Assets.play_sfx('ui.select', volume='ui')

    def _chandle_right_hud_drag_drop(self, event):
        origin, target = event.index
        if self.selected_unit == self.player_uid and origin != target:
            self.player.swap_item_slots(origin, target)
            Assets.play_sfx('ui.select', volume='ui')

    def _chandle_hud_portrait_select(self, event):
        unit = self.units[self.selected_unit]
        if 'shop' in unit.name.lower() and not self.gui.request('browse_showing'):
            self.toggle_shop()
        else:
            self._chandle_hud_portrait_inspect(event)

    def _chandle_hud_portrait_inspect(self, event):
        unit = self.units[self.selected_unit]
        self.gui.request('activate_tooltip', SpriteTitleLabel(unit.sprite, unit.name, unit.say, None))

    def _chandle_left_hud_inspect(self, event):
        aid = self.units[self.selected_unit].ability_slots[index]
        if aid is None:
            return
        ability = self.abilities[aid]
        self.gui.request('activate_tooltip', SpriteTitleLabel(
            ability.sprite, ability.name,
            ability.description(self.engine, self.selected_unit), None))

    def _chandle_left_hud_inspect(self, event):
        aid = self.units[self.selected_unit].ability_slots[event.index]
        if aid is None:
            return
        self.tooltip_ability(self.abilities[aid])

    def _chandle_right_hud_inspect(self, event):
        uid = self.selected_unit
        iid = self.engine.units[uid].item_slots[event.index]
        if iid is None:
            return
        item = ITEMS[iid]
        text = item.shop_text(self.engine, uid)
        self.gui.request('activate_tooltip', SpriteTitleLabel(
            item.sprite, item.shop_name, text, None))

    def _chandle_middle_hud_inspect(self, event):
        if event.index < 6:
            stat = [
                STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
                STAT.AIR, STAT.WATER, STAT.GOLD,
            ][event.index]
            current = self.engine.get_stats(self.selected_unit, stat)
            delta = self.engine.get_stats(self.selected_unit, stat, value_name=VALUE.DELTA)
            dval = round(s2ticks(delta)*60, 2)
            ds = ''
            if dval != 0:
                ds = f'\n{nsign_str(dval)} /m'
            s = f'{current:.2f}{ds}'
            title = f'{stat.name.lower().capitalize()}'
        elif event.index == 6:
            title = f'Respawn timer'
            s = 'Next respawn time in seconds'
        elif event.index == 7:
            title = 'Hitbox radius'
            s = 'Radius of hitbox'
        elif event.index == 8:
            title = f'Distance'
            s = f'Unit\'s distance from me'
        else:
            return
        self.gui.request('activate_tooltip', SpriteTitleLabel(STAT_SPRITES[event.index], title, s, None))

    def _chandle_status_hud_inspect(self, event):
        status = self.__last_hud_statuses[event.index]
        sprite = Assets.FALLBACK_SPRITE
        title = 'Unknown status'
        label = 'Missing tooltip'
        if status is STATUS.RESPAWN:
            sprite = Assets.get_sprite('mechanics.respawn')
            title = 'Respawn timer'
            label = 'Respawn time in seconds'
        elif status is STATUS.SHOP:
            shop_name, shop_color = Item.item_category_gui(self.engine.get_status(self.selected_unit, STATUS.SHOP))
            if shop_name is None:
                shop_name = 'no'
            sprite = Assets.get_sprite(f'units.{shop_name}-shop')
            title = f'{shop_name.capitalize()} Shop'
            label = f'Near {shop_name} shop'
        elif isinstance(status, STAT):
            sprite = Assets.get_sprite(f'mechanics.{status.name}')
            title = status.name.lower().capitalize()
            v = Mechanics.get_status(self.engine, self.selected_unit, status)
            sp = Mechanics.scaling(v)
            sp_asc = Mechanics.scaling(v, ascending=True)
            if status is STAT.STOCKS:
                label = f'Number of remaining deaths available before losing.'
            elif status is STAT.LOS:
                view_distance = self.units[self.selected_unit].view_distance
                label = f'Base view distance, obscured by [i]darkness[/i].\nActual view distance: [b]{view_distance}[/b]'
            elif status is STAT.DARKNESS:
                view_distance = self.units[self.selected_unit].view_distance
                label = f'Reducing view distance by [b]{int(100*sp_asc)}%[/b].\nActual view distance: [b]{view_distance}[/b]'
            elif status is STAT.MOVESPEED:
                speed = s2ticks(Mechanics.get_movespeed(self.engine, self.selected_unit)[0])
                label = f'Base movespeed, encumbered by [i]slow[/i].\nActual movement speed: [b]{round(speed)}/s[/b]'
            elif status is STAT.SLOW:
                label = f'Slowed by [b]{round(sp_asc*100)}%[/b]'
            elif status is STAT.SPIKES:
                label = f'Returns [b]{round(v)}[/b] [i]pure damage[/i] when hit by [i]normal damage[/i]'
            elif status is STAT.ARMOR:
                label = f'Reducing incoming [i]normal damage[/i] by [b]{round(sp_asc*100)}%[/b]'
            elif status is STAT.LIFESTEAL:
                label = f'Lifestealing [b]{round(v)}%[/b] of outgoing [i]normal damage[/i]'
            elif status is STAT.BOUNDED:
                label = f'Prevented from [i]moving[/i] or [i]teleporting[/i]'
            elif status is STAT.CUTS:
                label = f'Taking extra [b]{round(v)}[/b] [i]normal damage[/i] per hit'
            elif status is STAT.VANITY:
                label = f'Incoming [i]blast damage[/i] amplified by [b]{int(v)}%[/b]'
            elif status is STAT.REFLECT:
                label = f'Reflecting [b]{round(v)}%[/b] of incoming [i]blast damage[/i] as pure damage'
            elif status is STAT.SENSITIVITY:
                label = f'Amplifying incoming and outgoing [i]status effects[/i] by [b]{int(100*sp_asc)}%[/b]'
        elif status == 'fountain':
            sprite = Assets.get_sprite('units.fort')
            title = 'Fountain healing'
            label = 'Healing from a fountain'
        self.gui.request('activate_tooltip', SpriteTitleLabel(sprite, title, label, None))

    def _chandle_right_hud_activate(self, event):
        if self.selected_unit != self.player_uid:
            return
        self.player.sell_item(event.index)
        self.log_player_state()

    def _chandle_modal_select(self, event):
        self._chandle_modal_inspect(event)

    def _chandle_modal_inspect(self, event):
        item = ITEMS[event.index]
        self.gui.request('activate_tooltip', SpriteTitleLabel(
            item.sprite, item.shop_name, item.shop_text(self.engine, 0), None
        ))

    def _chandle_modal_activate(self, event):
        self.player.buy_item(event.index)
        self.log_player_state()

    def tooltip_ability(self, ability, uid=None):
        if uid is None:
            uid = self.selected_unit
        self.gui.request('activate_tooltip', SpriteTitleLabel(
            ability.sprite, ability.name,
            ability.description(self.engine, uid), None))
