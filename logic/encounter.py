import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np

from nutil.vars import NP, nsign_str
from nutil.random import SEED
from nutil.display import njoin, make_title
from nutil.time import RateCounter
from nutil.vars import modify_color, List

from data import resource_name
from data.load import RDF
from data.settings import Settings
from data.assets import Assets
from gui.api import SpriteLabel, SpriteTitleLabel, ProgressBar

from engine.common import *
from engine.api import EncounterAPI as BaseEncounterAPI
from engine.encounter import Encounter as EncounterEngine

from logic.data import ABILITIES
from logic.mechanics import Mechanics
from logic.mapgen import MapGenerator
from logic.items import ITEM, ITEMS, ITEM_CATEGORIES


RNG = np.random.default_rng()
STAT_SPRITES = tuple(Assets.get_sprite('ability', s) for s in ('physical', 'fire', 'earth', 'air', 'water', 'gold'))
MODAL_MODES = ['abilities', 'items', 'shop', 'shop']


class EncounterAPI(BaseEncounterAPI):
    RNG = np.random.default_rng()

    # Logic handlers
    def hp_zero(self, uid):
        unit = self.engine.units[uid]
        logger.debug(f'Unit {unit.name} died')
        self.engine.units[uid].hp_zero()

    def status_zero(self, uid, status):
        unit = self.engine.units[uid]
        status = list(STATUS)[status]
        logger.debug(f'Unit {unit.name} lost status {status.name}')
        self.engine.units[uid].status_zero(status)

    # GUI handlers
    @property
    def general_label_text(self):
        s = [
            f'{self.time_str}',
        ]
        if self.dev_mode:
            s.insert(0, 'DEV MODE')
            s.extend([
                '\n__ RP Table __',
                '5 rp =  9 %',
                '10 rp = 17 %',
                '20 rp = 30 %',
                '30 rp = 38 %',
                '40 rp = 44 %',
                '50 rp = 50 %',
                '100 rp = 67 %',
                '150 rp = 75 %',
                '200 rp = 80 %',
            ])
        return '\n'.join(s)

    @property
    def general_label_color(self):
        return (0,0,0,0) if not self.dev_mode else (0.5,0,1,0.4)

    @property
    def control_buttons(self):
        return ['Pause' if self.engine.auto_tick else 'Play', 'Abilities', 'Items', 'Shop']

    def control_button_click(self, index):
        if index == 0:
            self.toggle_play()
            self.set_modal_mode(None, toggle_play=False)
        elif index == 1: self.set_modal_mode('abilities')
        elif index == 2: self.set_modal_mode('items')
        elif index == 3: self.set_modal_mode('shop')

    @property
    def show_menu(self):
        return not self.engine.auto_tick and not self.dev_mode and not self.modal_mode

    def quickcast(self, ability_index, target):
        # Ability from player input (requires handling user feedback)
        aid = self.units[0].abilities[ability_index]
        if aid is None:
            return
        ability = self.abilities[aid]
        r = self.units[0].use_ability(aid, target)
        if r is None:
            logger.warning(f'Ability {ability.__class__} failed to return a result!')
        if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
            Assets.play_sfx('ui', FAIL_SFX[r], replay=False,
                volume=Settings.get_volume('feedback'))
        if r is not FAIL_RESULT.INACTIVE:
            self.engine.add_visual_effect(VisualEffect.SPRITE, 15, {
                'point': target,
                'fade': 30,
                'category': 'ui',
                'source': 'crosshair',
                'size': (40, 40),
                'tint': ability.color,
            })

    def itemcast(self, item_index, target):
        iid = self.units[0].item_slots[item_index]
        if iid is None:
            return
        item = ITEMS[iid]
        r = item.quickcast(self, 0, target)
        if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
            Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')

    def itemsell(self, item_index, target):
        iid = self.units[0].item_slots[item_index]
        if iid is None:
            return
        item = ITEMS[iid]
        r = item.sell_item(self.engine, 0)
        if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
            Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')
        else:
            Assets.play_sfx('ability', 'shop', volume=Settings.get_volume('feedback'))

    def ability_sort(self, ability_index, target):
        List.move_bottom(self.units[0].abilities, ability_index)

    def item_sort(self, item_index, target):
        List.move_bottom(self.units[0].item_slots, item_index)

    def user_hotkey(self, hotkey, target):
        if hotkey == 'toggle_play':
            self.toggle_play()
        elif hotkey == 'dev1':
            self.debug(dev_mode=None)
        elif hotkey == 'dev2':
            self.show_debug = not self.show_debug
        elif hotkey == 'dev3':
            self.show_debug = not self.show_debug
        elif hotkey == 'dev4':
            self.debug(tick=1)
        elif 'control' in hotkey:
            control = int(hotkey[-1])
            if control == 0:
                self.selected_unit = 0
                if self.modal_mode is None:
                    self.toggle_play()
                else:
                    self.set_modal_mode(None)
            elif 0 < control < 4:
                self.set_modal_mode(MODAL_MODES[control-1])

    def set_modal_mode(self, new_mode, toggle_play=True):
        if new_mode == self.modal_mode:
            self.modal_mode = None
        else:
            self.modal_mode = new_mode
        if toggle_play:
            self.toggle_play(self.modal_mode is None)

    @property
    def map_size(self):
        return self.map.size

    @property
    def map_image_source(self):
        return self.map.image

    @property
    def request_redraw(self):
        return self.map.request_redraw

    def get_visible_uids(self, view_size):
        max_los = self.player_los
        if self.dev_mode:
            max_los = max(max_los, np.linalg.norm(np.array(view_size) / 2))
        in_los = self.engine.unit_distance(0) <= max_los
        is_neutral = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) < 0
        is_special = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) >= 1000
        is_ally = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) == self.engine.get_stats(0, STAT.ALLEGIANCE)
        return in_los | is_neutral | is_special | is_ally

    # Agent viewer
    def agent_panel_name(self):
        return self.units[self.selected_unit].name

    def agent_panel_bars(self):
        uid = self.selected_unit
        hp = self.engine.get_stats(uid, STAT.HP)
        max_hp = self.engine.get_stats(uid, STAT.HP, value_name=VALUE.MAX)
        delta_hp = self.engine.get_stats(uid, STAT.HP, value_name=VALUE.DELTA)
        delta_hp = f'{nsign_str(round(self.engine.s2ticks(delta_hp), 1))} /s'
        mana = self.engine.get_stats(uid, STAT.MANA)
        max_mana = self.engine.get_stats(uid, STAT.MANA, value_name=VALUE.MAX)
        delta_mana = self.engine.get_stats(uid, STAT.MANA, value_name=VALUE.DELTA)
        delta_mana = f'{nsign_str(round(self.engine.s2ticks(delta_mana), 1))} /s'
        return [
            ProgressBar(hp/max_hp, f'HP: {hp:.1f}/{max_hp:.1f} {delta_hp}', (1, 0, 0, 1)),
            ProgressBar(mana/max_mana, f'Mana: {mana:.1f}/{max_mana:.1f} {delta_mana}', (0, 0, 1, 1)),
        ]

    def agent_panel_boxes(self):
        uid = self.selected_unit
        current = self.engine.get_stats(uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
            STAT.AIR, STAT.WATER, STAT.GOLD,
        ])
        delta = self.engine.get_stats(uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
            STAT.AIR, STAT.WATER, STAT.GOLD,
        ], value_name=VALUE.DELTA)
        stats = []
        for i in range(6):
            dval = round(self.engine.s2ticks(delta[i])*60, 1)
            ds = ''
            if dval != 0:
                ds = f'     {nsign_str(dval)} /m'
            stats.append(f'{math.floor(current[i])}{ds}')
        return tuple(SpriteLabel(STAT_SPRITES[i], f'{stats[i]}', None) for i in range(6))

    def agent_panel_label(self):
        uid = self.selected_unit
        player_dist = self.engine.unit_distance(0, uid)
        velocity = self.engine.s2ticks(self.engine.get_velocity(uid))
        return '\n'.join([
            f'Speed: {velocity:.1f}',
            f'Distance: {player_dist:.1f}',
            '',
            *self.status_summary(uid),
        ])

    def status_summary(self, uid):
        def get(s):
            return Mechanics.get_status(self.engine, uid, s)
        def format_time(t):
            return math.ceil(self.engine.ticks2s(t))
        def format_rp(v):
            return round((1-Mechanics.rp2reduction(v))*100)

        strs = []
        respawn = self.engine.get_status(uid, STATUS.RESPAWN)
        if respawn > 0:
            duration = self.engine.get_status(uid, STATUS.RESPAWN, STATUS_VALUE.DURATION)
            strs.append(f'Respawning in {format_time(duration)}s')

        if self.engine.get_status(uid, STATUS.FOUNTAIN) > 0:
            strs.append(f'~ Fountain ~')

        shop = self.engine.get_status(uid, STATUS.SHOP)
        if shop > 0:
            shop = list(ITEM_CATEGORIES)[round(shop)-1].name.lower().capitalize()
            strs.append(f'At shop: {shop}')

        for stat, status in Mechanics.STATUSES.items():
            v = get(stat)
            if v > 0:
                name = stat.name.lower().capitalize()
                duration = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
                ds = f'* {format_time(duration)}s' if duration > 0 else ''
                strs.append(f'{round(v)}/{format_rp(v)}% {name}{ds}')

        for status in [STATUS.SLOW]:
            d = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
            v = self.engine.get_status(uid, status, STATUS_VALUE.STACKS)
            if d > 0:
                name = status.name.lower().capitalize()
                ds = f'* {format_time(d)}s'
                strs.append(f'{round(v)}/{format_rp(v)}% {name}{ds}')

        return strs

    # HUD
    def hud_sprite_labels(self):
        sls = []
        for aid in self.units[0].abilities:
            if aid is None:
                sls.append(SpriteLabel(str(Assets.FALLBACK_SPRITE), '', (0,0,0,0)))
                continue
            ability = self.abilities[aid]
            sprite = Assets.get_sprite('ability', ability.sprite)
            s, color = ability.gui_state(self.engine, 0)
            s = f'{ability.name}\n{s}'
            sls.append(SpriteLabel(sprite, s, modify_color(color, a=0.4)))
        return sls

    def hud_aux_sprite_labels(self):
        sls = []
        for iid in self.units[0].item_slots:
            if iid is None:
                sls.append(SpriteLabel(Assets.get_sprite('ui', 'empty'), '', (0,0,0,0)))
                continue
            item = ITEMS[iid]
            sprite = Assets.get_sprite('ability', item.name)
            s, color = item.gui_state(self.engine, 0)
            s = f'{item.name}\n{s}'
            sls.append(SpriteLabel(sprite, s, modify_color(color, a=0.4)))
        return sls

    # Modal
    @property
    def show_modal_grid(self):
        return self.modal_mode in {'abilities', 'items'}

    @property
    def show_modal_browse(self):
        return self.modal_mode == 'shop'

    def modal_browse_main(self):
        item = ITEMS[self.shop_browse_item]
        return SpriteTitleLabel(
            Assets.get_sprite('ability', item.name),
            item.shop_name, item.shop_text(self.engine, 0),
            modify_color(item.color, a=0.5))

    def modal_browse_sts(self):
        sts = []
        near_shop = self.engine.get_status(0, STATUS.SHOP) > 0
        for item in ITEMS:
            active = False
            if near_shop:
                active = item.check_buy(self.engine, 0)
            a = 0.7 if active is True else 0.3
            color = modify_color(item.color, a=a)
            sts.append(SpriteLabel(
                Assets.get_sprite('ability', item.name), item.shop_name, color))
        return sts

    def modal_grid(self):
        if self.modal_mode == 'abilities':
            return self.modal_abilities()
        if self.modal_mode == 'items':
            return self.modal_items()

    def modal_abilities(self):
        sts = []
        for aid in self.engine.units[self.selected_unit].abilities:
            if aid is None:
                sts.append(SpriteTitleLabel(str(Assets.FALLBACK_SPRITE), '', '', (0, 0, 0, 0)))
                continue
            ability = self.abilities[aid]
            color = modify_color(ability.color, a=0.3)
            sts.append(SpriteTitleLabel(
                Assets.get_sprite('ability', ability.name), ability.name,
                ability.description(self.engine, self.selected_unit), color))
        return sts

    def modal_items(self):
        sts = []
        for iid in self.engine.units[self.selected_unit].item_slots:
            if iid is None:
                sts.append(SpriteTitleLabel(
                    Assets.get_sprite('ui', 'empty'), 'Empty Slot', '', (0, 0, 0, 0)))
                continue
            item = ITEMS[iid]
            color = modify_color(item.color, a=0.3)
            text = item.shop_text(self.engine, 0)
            sts.append(SpriteTitleLabel(
                Assets.get_sprite('ability', item.name), item.name, text, color))
        return sts

    def modal_click(self, index, button):
        if button == 'right' and self.modal_mode == 'shop':
            r = ITEMS[index].buy_item(self.engine, 0)
            if not isinstance(r, FAIL_RESULT):
                Assets.play_sfx('ability', 'shop', volume='feedback')
                return
            if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
                Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')
        if button == 'left' and self.modal_mode == 'shop':
            self.shop_browse_item = ITEMS[index].iid

    # Misc
    abilities = ABILITIES

    @property
    def unit_count(self):
        return len(self.units)

    def pretty_stats(self, uid, stats=None):
        unit = self.units[uid]
        if stats is None:
            stats = STAT
        stat_table = self.engine.stats.table
        velocity = self.engine.get_velocity(uid)
        s = [
            f'Speed: {self.engine.s2ticks(velocity):.2f}/s ({velocity:.2f}/t)',
        ]
        for stat in stats:
            current = stat_table[uid, stat, VALUE.CURRENT]
            delta = self.engine.s2ticks()*stat_table[uid, stat, VALUE.DELTA]
            d_str = f' + {delta:.2f}' if delta != 0 else ''
            max_value = stat_table[uid, stat, VALUE.MAX]
            mv_str = f' / {max_value:.2f}' if max_value < 100_000 else ''
            s.append(f'{stat.name.lower().capitalize()}: {current:3.2f}{d_str}{mv_str}')
        return njoin(s)

    def pretty_statuses(self, uid):
        t = []
        for status in STATUS:
            d = self.engine.get_status(uid, status, value_name=STATUS_VALUE.DURATION)
            s = self.engine.get_status(uid, status, value_name=STATUS_VALUE.STACKS)
            if d > 0:
                name_ = status.name.lower().capitalize()
                t.append(f'{name_}: {self.engine.ticks2s(d):.2f} × {s:.2f}')
        return njoin(t) if len(t) > 0 else 'No statuses'

    def pretty_cooldowns(self, uid):
        s = []
        for ability in ABILITY:
            v = self.engine.get_cooldown(uid, ability)
            if v > 0:
                name_ = ability.name.lower().capitalize()
                s.append(f'{name_}: {self.engine.ticks2s(v):.2f} ({round(v)})')
        return njoin(s) if len(s) > 0 else 'No cooldowns'

    def debug_panel_labels(self):
        uid = self.selected_unit
        unit = self.engine.units[uid]
        text_unit = '\n'.join([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            f'{self.pretty_stats(uid)}',
            make_title(f'Status', length=30),
            f'{self.pretty_statuses(uid)}',
            make_title(f'Cooldown', length=30),
            f'{self.pretty_cooldowns(uid)}',
            f'Abilities: {unit.abilities}',
            f'Items: {unit.item_slots}',
            make_title(f'Debug', length=30),
            f'{unit.debug_str}',
            f'Action phase: {unit.uid % self.engine.AGENCY_PHASE_COUNT}',
            f'Agency: {self.engine.timers["agency"][unit.uid].mean_elapsed_ms:.3f} ms',
        ])

        timer_strs = []
        for tname, timer in self.engine.timers.items():
            if isinstance(timer, RateCounter):
                timer_strs.append(f'- {tname}: {timer.mean_elapsed_ms:.3f} ms')
        text_performance = njoin([
            make_title('Logic Performance', length=30),
            f'Game time: {self.time_str}',
            f'Tick: {self.engine.tick} +{self.engine.s2ticks()} t/s',
            *timer_strs,
            f'Map size: {self.map_size}',
            f'Agency phase: {self.engine.tick % self.engine.AGENCY_PHASE_COUNT}',
        ])
        return text_performance, text_unit

    def __init__(self, game, player_abilities):
        self.dev_mode = False
        self.show_debug = False
        self.modal_mode = None
        self.shop_browse_item = ITEMS[0].iid
        self.game = game
        self.engine = EncounterEngine(self)
        self.map = MapGenerator(self)
        a = list(ABILITY)
        self.engine.units[0].abilities = player_abilities
        # Setup units
        for unit in self.engine.units:
            unit.action_phase()
        Assets.play_sfx('ui', 'play', volume=Settings.get_volume('feedback'))

    def debug(self, *args, dev_mode=-1, tick=None, tps=None, **kwargs):
        logger.debug(f'Logic Debug called (extra args: {args} {kwargs})')
        self.engine.set_tps(tps)
        if dev_mode == -1:
            dev_mode = self.dev_mode
        elif dev_mode == None:
            dev_mode = not self.dev_mode
        self.dev_mode = dev_mode
        if tick is not None:
            self.engine._do_ticks(tick)


FAIL_SFX = {
    FAIL_RESULT.INACTIVE: 'pause',
    FAIL_RESULT.MISSING_COST: 'cost',
    FAIL_RESULT.MISSING_TARGET: 'target',
    FAIL_RESULT.OUT_OF_BOUNDS: 'range',
    FAIL_RESULT.OUT_OF_RANGE: 'range',
    FAIL_RESULT.ON_COOLDOWN: 'cooldown',
}
