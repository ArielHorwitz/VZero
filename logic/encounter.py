import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np

from nutil.vars import collide_point, NP
from nutil.random import SEED
from nutil.display import njoin, make_title
from nutil.time import RateCounter
from nutil.vars import modify_color

from data import resource_name
from data.load import RDF
from data.settings import Settings
from data.assets import Assets
from gui.api import SpriteLabel, SpriteTitleLabel, ProgressBar

from engine.common import *
from engine.api import EncounterAPI as BaseEncounterAPI
from engine.encounter import Encounter as EncounterEngine

from logic.data import ABILITIES
from logic.mapgen import MapGenerator
from logic.items import ITEM, ITEMS


RNG = np.random.default_rng()
STAT_SPRITES = tuple(Assets.get_sprite('ability', s) for s in ('physical', 'fire', 'earth', 'air', 'water', 'gold'))
MODAL_MODES = ['shop', 'abilities', 'abilities', 'abilities']


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
        self.units[0].abilities[ability_index], self.units[0].abilities[ability_index-1] = self.units[0].abilities[ability_index-1], self.units[0].abilities[ability_index]

    def item_sort(self, item_index, target):
        self.units[0].item_slots[item_index], self.units[0].item_slots[item_index-1] = self.units[0].item_slots[item_index-1], self.units[0].item_slots[item_index]

    def user_hotkey(self, hotkey, target):
        if 'toggle_play' in hotkey:
            self.toggle_play()
        elif 'modal' in hotkey:
            new_mode = MODAL_MODES[int(hotkey[-1])-1]
            if new_mode == self.modal_mode and self.show_modal:
                self.show_modal = False
            else:
                self.show_modal = True
                self.modal_mode = new_mode

    @property
    def map_size(self):
        return self.map.size

    @property
    def map_image_source(self):
        return self.map.image

    @property
    def request_redraw(self):
        return self.map.request_redraw

    # Agent viewer
    def agent_panel_name(self):
        return self.units[self.selected_unit].name

    def agent_panel_bars(self):
        uid = self.selected_unit
        hp = self.engine.get_stats(uid, STAT.HP)
        max_hp = self.engine.get_stats(uid, STAT.HP, value_name=VALUE.MAX)
        mana = self.engine.get_stats(uid, STAT.MANA)
        max_mana = self.engine.get_stats(uid, STAT.MANA, value_name=VALUE.MAX)
        return [
            ProgressBar(hp/max_hp, f'HP: {hp:.1f}/{max_hp:.1f}', (1, 0, 0, 1)),
            ProgressBar(mana/max_mana, f'Mana: {mana:.1f}/{max_mana:.1f}', (0, 0, 1, 1)),
        ]

    def agent_panel_boxes(self):
        uid = self.selected_unit
        stats = self.engine.get_stats(uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
            STAT.AIR, STAT.WATER, STAT.GOLD,
        ])
        return tuple(SpriteLabel(STAT_SPRITES[i], f'{stats[i]:.1f}', None) for i in range(6))

    def agent_panel_label(self):
        uid = self.selected_unit
        dist = self.engine.unit_distance(0, uid)
        v = self.engine.s2ticks(self.engine.get_velocity(uid))
        return '\n'.join([
            f'Speed: {v:.1f}',
            f'Distance: {dist:.1f}',
            '',
            self.pretty_statuses(uid),
        ])

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
                sls.append(SpriteLabel(str(Assets.FALLBACK_SPRITE), '', (0,0,0,0)))
                continue
            item = ITEMS[iid]
            sprite = Assets.get_sprite('ability', item.name)
            s, color = item.gui_state(self.engine, 0)
            s = f'{item.name}\n{s}'
            sls.append(SpriteLabel(sprite, s, modify_color(color, a=0.4)))
        return sls

    # Modal
    def modal_stls(self):
        if self.modal_mode == 'shop':
            return self.modal_shop()
        if self.modal_mode == 'abilities':
            return self.modal_abilities()

    def modal_shop(self):
        stls = []
        shoppable_items = [item for item in ITEMS if item.check_shop(self.engine, 0)]
        active_items = [item.check_buy(self.engine, 0) for item in ITEMS]
        if len(shoppable_items) == 0:
            shoppable_items = ITEMS
        for item in shoppable_items:
            active = active_items[item.iid] is True
            color = modify_color(item.color, a=0.7 if active else 0.2)
            name, text = item.shop_text
            stl = SpriteTitleLabel(
                Assets.get_sprite('ability', item.name),
                name, text, color)
            stls.append(stl)
        return stls

    def modal_abilities(self):
        stls = []
        for aid in self.engine.units[self.selected_unit].abilities:
            if aid is None:
                stls.append(SpriteTitleLabel(str(Assets.FALLBACK_SPRITE), '', '', (0, 0, 0, 0)))
                continue
            ability = self.abilities[aid]
            color = modify_color(ability.color, a=0.3)
            stl = SpriteTitleLabel(
                Assets.get_sprite('ability', ability.name),
                ability.name, ability.description(self.engine, self.selected_unit), color)
            stls.append(stl)
        return stls

    def modal_click(self, index, button):
        if button == 'right' and self.modal_mode == 'shop':
            r = ITEMS[index].buy_item(self.engine, 0)
            if not isinstance(r, FAIL_RESULT):
                Assets.play_sfx('ability', 'shop', volume='feedback')
                return
            if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
                Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')

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
            f'Allegience: {unit.allegiance}',
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
        s = []
        for status in STATUS:
            v = self.engine.stats.status_table[uid, status]
            duration = self.engine.ticks2s(v[STATUS_VALUE.DURATION])
            if duration > 0:
                name_ = status.name.lower().capitalize()
                stacks = v[STATUS_VALUE.STACKS]
                s.append(f'{name_}: {duration:.2f} × {stacks:.2f}')
        return njoin(s) if len(s) > 0 else 'No statuses'

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
        self.modal_mode = 'shop'
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


class OldEncounterAPI:
    # UTILITY
    def mask_alive(self):
        return self.get_stats(slice(None), STAT.HP) > 0

    def mask_dead(self):
        return np.invert(self.mask_alive())

    def mask_allies(self, uid):
        a = self.units[uid].allegiance
        return np.array([_u.allegiance == a for _u in self.units])

    def mask_enemies(self, uid):
        return np.invert(self.mask_allies(uid))

    def nearest_uid(self, point, mask=None, alive_only=True):
        if mask is None:
            mask = np.ones(len(self.units), dtype=np.int)
        if alive_only:
            mask = np.logical_and(mask, self.get_stats(slice(None), STAT.HP) > 0)
        if mask.sum() == 0:
            return None, None
        distances = self.e.stats.get_distances(point)
        uid = NP.argmin(distances, mask)
        return uid, distances[uid]

    def get_offset(self):
        return RNG.random(2) * 30

    def random_location(self):
        return np.array(tuple(SEED.r*_ for _ in self.map_size))

    def get_live_monster_count(self):
        return (self.get_stats(slice(None), STAT.HP)>0).sum()


FAIL_SFX = {
    FAIL_RESULT.INACTIVE: 'pause',
    FAIL_RESULT.MISSING_COST: 'cost',
    FAIL_RESULT.MISSING_TARGET: 'target',
    FAIL_RESULT.OUT_OF_BOUNDS: 'range',
    FAIL_RESULT.OUT_OF_RANGE: 'range',
    FAIL_RESULT.ON_COOLDOWN: 'cooldown',
}
