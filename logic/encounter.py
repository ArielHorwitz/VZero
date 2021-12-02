import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np

from nutil.vars import collide_point, NP
from nutil.random import SEED
from nutil.display import njoin, make_title
from nutil.time import ratecounter, RateCounter
from nutil.vars import modify_color

from data import resource_name
from data.load import RDF
from data.settings import Settings
from data.assets import Assets
from gui.api import SpriteLabel, SpriteTitleLabel, ProgressBar

from engine.common import *
from engine.api import EncounterAPI as BaseEncounterAPI
from engine.encounter import Encounter as EncounterEngine

from logic.mapgen import MapGenerator
from logic.items import items


RNG = np.random.default_rng()
STAT_SPRITES = tuple(Assets.get_sprite('ability', s) for s in ('physical', 'fire', 'earth', 'air', 'water', 'gold'))
MODAL_MODES = ['shop', 'abilities', 'shop', 'shop']


class EncounterAPI(BaseEncounterAPI):
    RNG = np.random.default_rng()

    # Abilities
    @property
    def abilities(self):
        return self.game.abilities

    def use_ability(self, uid, aid, target):
        if uid == 0:
            logger.debug(f'uid {uid} casting ability {aid.name} to {target}')

        with ratecounter(self.engine.timers['ability_single']):
            if not self.engine.auto_tick and not self.dev_mode:
                return FAIL_RESULT.INACTIVE

            if self.engine.stats.get_stats(uid, STAT.HP, VALUE.CURRENT) <= 0:
                logger.warning(f'Unit {uid} is dead and requested ability {aid.name}')
                return FAIL_RESULT.INACTIVE

            target = np.array(target)
            if (target > self.map_size).any() or (target < 0).any():
                return FAIL_RESULT.OUT_OF_BOUNDS

            ability = self.game.abilities[aid]
            r = ability.cast(self.engine, uid, target)
            if r is None:
                m = f'Ability {ability.__class__} cast() method returned None. Must return FAIL_RESULT on fail or aid on success.'
                logger.error(m)
                raise ValueError(m)
            if isinstance(r, FAIL_RESULT):
                # logger.debug(f'uid {uid} tried casting {aid.name} but failed with {r.name}')
                pass
            else:
                Assets.play_sfx('ability', ability.name, volume=Settings.get_volume('sfx'))
            return r

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
        aid = self.engine.units[0].abilities[ability_index]
        r = self.use_ability(0, aid, target)
        if r is None:
            logger.warning(f'Ability {self.abilities[aid].__class__} failed to return a result!')
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
            })

        self.use_ability(0, aid, target)

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
            ability = self.abilities[aid]
            sprite = Assets.get_sprite('ability', ability.sprite)
            cast_state = ability.gui_state(self.engine, 0)
            s, color = cast_state
            s = f'{ability.name}\n{s}'
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
        for i, item in enumerate(items.ITEM):
            item_active = all([
                self.active_shop_items[i],
                items.Shop.check_cost(self.engine, 0, items.ITEM_LIST[i]),
            ])
            color = modify_color(self.item_colors[i], a=0.5 if item_active else 0.2)
            stl = SpriteTitleLabel(
                Assets.get_sprite('ability', item.name),
                item.name, self.item_texts[i], color)
            stls.append(stl)
        return stls

    def modal_abilities(self):
        stls = []
        for aid in self.engine.units[0].abilities:
            ability = self.abilities[aid]
            color = modify_color(ability.color, a=0.3)
            stl = SpriteTitleLabel(
                Assets.get_sprite('ability', ability.name),
                ability.name, ability.description(self.engine, 0), color)
            stls.append(stl)
        return stls

    def modal_click(self, index, button):
        if button == 'right' and self.modal_mode == 'shop':
            r = items.Shop.buy_item(self.engine, 0, index)
            if not isinstance(r, FAIL_RESULT):
                Assets.play_sfx('ability', 'shop', volume=Settings.get_volume('feedback'))
                return
            Assets.play_sfx('ui', 'target', volume=Settings.get_volume('feedback'))

    item_texts = [f'{items.item_repr(item)}' for item in items.ITEM]
    item_colors = [items.ICAT_COLORS[items.ITEM_STATS[item].category-1] for item in items.ITEM]

    @property
    def active_shop_items(self):
        item_categories = np.array([items.ITEM_STATS[item].category.value for item in items.ITEM])
        active_category = self.engine.get_status(0, STATUS.SHOP)
        active_items = item_categories == active_category
        return active_items

    # Debug / Misc
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
        self.engine.units[0].abilities = [a[_] for _ in player_abilities]
        # Setup units
        for unit in self.engine.units:
            unit.action_phase()

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

    @property
    def add_visual_effect(self):
        return self.e.add_visual_effect

    # PROPERTIES
    @property
    def mod_api(self):
        return self.e.mod_api

    @property
    def dev_mode(self):
        return self.e.dev_mode

    @classmethod
    def get_ability(cls, index):
        return self.game.abilities[index]

    @property
    def abilities(self):
        return self.game.abilities

    @property
    def map_size(self):
        return self.e.mod_api.map_size

    @property
    def map_center(self):
        return self.map_size / 2

    @property
    def auto_tick(self):
        return self.e.auto_tick

    @property
    def unit_count(self):
        return self.e.unit_count

    @property
    def tick(self):
        return self.e.tick

    @property
    def units(self):
        return self.e.units

    def debug_stats_table(self):
        return str(self.e.stats.table)

    # GUI UTILITIES - do not use for mechanics
    def do_ticks(self, t=1):
        return self.e._do_ticks(t)

    def set_auto_tick(self, *a, **k):
        return self.e.set_auto_tick(*a, **k)

    def update(self):
        self.e.update()

    def get_visual_effects(self):
        return self.e.get_visual_effects()

    @property
    def map_image_source(self):
        return self.e.mod_api.map_image_source

    def use_ability(self, *args, **kwargs):
        return self.e.use_ability(*args, **kwargs)

    @property
    def timers(self):
        return self.e.timers

    @property
    def request_redraw(self):
        return self.e.mod_api.request_redraw

    # DEBUG / MISC
    def __init__(self, encounter):
        self.e = encounter

    @property
    def debug(self):
        return self.e.debug_action


FAIL_SFX = {
    FAIL_RESULT.INACTIVE: 'pause',
    FAIL_RESULT.MISSING_COST: 'cost',
    FAIL_RESULT.MISSING_TARGET: 'target',
    FAIL_RESULT.OUT_OF_BOUNDS: 'range',
    FAIL_RESULT.OUT_OF_RANGE: 'range',
    FAIL_RESULT.ON_COOLDOWN: 'cooldown',
}
