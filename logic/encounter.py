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


class EncounterAPI(BaseEncounterAPI):
    RNG = np.random.default_rng()
    enc_over = False
    win = False

    # Logic handlers
    def hp_zero(self, uid):
        unit = self.engine.units[uid]
        logger.debug(f'Unit {unit.name} died')
        if unit.lose_on_death or unit.win_on_death:
            self.enc_over = True
            self.win = unit.win_on_death
            self.toggle_play(set_to=False)
            self.raise_gui_flag('menu')
        else:
            self.engine.units[uid].hp_zero()

    def status_zero(self, uid, status):
        unit = self.engine.units[uid]
        status = list(STATUS)[status]
        logger.debug(f'Unit {unit.name} lost status {status.name}')
        self.engine.units[uid].status_zero(status)

    # GUI handlers
    @property
    def menu_text(self):
        if self.enc_over:
            if self.win:
                return f'You win!\nScore: {self.score}'
            else:
                return f'You lose :(\nScore: {self.score}'
        else:
            return f'Paused\nScore: {self.score}'

    @property
    def general_label_text(self):
        s = [
            f'{self.time_str} - {self.score} score',
        ]
        if self.dev_mode:
            s.insert(0, 'DEBUG MODE - ')
        return ''.join(s)

    @property
    def general_label_color(self):
        return (1,1,1,1) if not self.dev_mode else (0.5,0,1,1)

    @property
    def control_buttons(self):
        return ['Pause' if self.engine.auto_tick else 'Play', 'Shop']

    def control_button_click(self, index):
        if index == 0:
            self.toggle_play()
        elif index == 1:
            self.selected_unit = 0
            self.raise_gui_flag('browse_toggle')

    def quickcast(self, ability_index, target):
        # Ability from player input (requires handling user feedback)
        aid = self.units[0].abilities[ability_index]
        if aid is None:
            return
        ability = self.abilities[aid]
        r = self.units[0].use_ability(aid, target)
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
        r = self.units[0].use_item(iid, target)
        if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
            Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')
        if r not in (FAIL_RESULT.INACTIVE, FAIL_RESULT.MISSING_ACTIVE):
            a = ITEMS[iid].ability
            color = (1,1,1,1) if a is None else a.color
            self.engine.add_visual_effect(VisualEffect.SPRITE, 15, {
                'point': target,
                'fade': 30,
                'category': 'ui',
                'source': 'crosshair',
                'size': (40, 40),
                'tint': color,
            })

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

    def user_hotkey(self, hotkey, target):
        if hotkey == 'toggle_play':
            self.toggle_play()
        elif hotkey == 'dev1':
            if Settings.get_setting('dev_build', 'General'):
                self.debug(dev_mode=None, test=True)
        elif hotkey == 'dev2':
            self.show_debug = not self.show_debug
        elif hotkey == 'dev3':
            self.debug(tick=1)
        elif hotkey == 'dev4':
            self.engine.set_auto_tick()
        elif 'control' in hotkey:
            control = int(hotkey[-1])
            if control == 0:
                self.toggle_play()
            elif control == 1:
                self.selected_unit = 0
                self.raise_gui_flag('browse_toggle')

    @property
    def map_size(self):
        return self.map.size

    @property
    def map_image_source(self):
        return self.map.image

    @property
    def request_redraw(self):
        return self.map.request_redraw

    # Sprites
    def sprite_visible_mask(self, view_size):
        max_los = self.player_los
        if self.dev_mode:
            max_los = max(max_los, np.linalg.norm(np.array(view_size) / 2))
        in_los = self.engine.unit_distance(0) <= max_los
        is_neutral = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) < 0
        is_special = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) >= 1000
        is_ally = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) == self.engine.get_stats(0, STAT.ALLEGIANCE)
        return in_los | is_neutral | is_special | is_ally

    def sprite_bars(self):
        max_hps = self.engine.get_stats(slice(None), STAT.HP, value_name=VALUE.MAX)
        hps = self.engine.get_stats(slice(None), STAT.HP) / max_hps
        max_manas = self.engine.get_stats(slice(None), STAT.MANA, value_name=VALUE.MAX)
        manas = self.engine.get_stats(slice(None), STAT.MANA) / max_manas
        manas[hps<=0] = 0
        return hps, manas

    def sprite_statuses(self, uid):
        icons = []
        respawn = self.engine.get_status(uid, STATUS.RESPAWN)
        if respawn > 0:
            duration = self.engine.get_status(uid, STATUS.RESPAWN, STATUS_VALUE.DURATION)
            icons.append(Assets.get_sprite('ability', 'respawn'))

        if self.engine.get_status(uid, STATUS.FOUNTAIN) > 0:
            icons.append(Assets.get_sprite('unit', 'fort'))

        shop = self.engine.get_status(uid, STATUS.SHOP)
        if shop > 0:
            shop = list(ITEM_CATEGORIES)[round(shop)-1].name.lower().capitalize()
            icons.append(Assets.get_sprite('unit', 'basic-shop'))

        for status in [*Mechanics.STATUSES.values()]:
            d = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
            if d > 0:
                name = status.name.lower().capitalize()
                icons.append(Assets.get_sprite('ability', name))

        return icons

    # HUD
    def hud_left(self):
        uid = self.selected_unit
        sls = []
        for aid in self.units[uid].abilities:
            if aid is None:
                sls.append(SpriteLabel(str(Assets.get_sprite('ui', 'blank')), '', (0,0,0,0)))
                continue
            ability = self.abilities[aid]
            sprite = Assets.get_sprite('ability', ability.sprite)
            s, color = ability.gui_state(self.engine, uid)
            sls.append(SpriteLabel(sprite, s, modify_color(color, a=0.4)))
        return sls

    def hud_right(self):
        uid = self.selected_unit
        sls = []
        for iid in self.units[uid].item_slots:
            if iid is None:
                sls.append(SpriteLabel(Assets.get_sprite('ui', 'blank'), '', (0,0,0,0)))
                continue
            item = ITEMS[iid]
            sprite = Assets.get_sprite('ability', item.name)
            s, color = item.gui_state(self.engine, uid)
            sls.append(SpriteLabel(sprite, s, modify_color(color, a=0.4)))
        return sls

    def hud_middle(self):
        uid = self.selected_unit
        current = self.engine.get_stats(uid, [
            STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
            STAT.AIR, STAT.WATER, STAT.GOLD,
        ])
        return tuple(SpriteLabel(STAT_SPRITES[i], f'{math.floor(current[i])}', (0,0,0,0)) for i in range(6))

    def hud_statuses(self):
        def get(s):
            return Mechanics.get_status(self.engine, uid, s)
        def format_time(t):
            return math.ceil(self.engine.ticks2s(t))
        def format_rp(v):
            return round((1-Mechanics.rp2reduction(v))*100)

        uid = self.selected_unit
        strs = []
        respawn = self.engine.get_status(uid, STATUS.RESPAWN)
        if respawn > 0:
            duration = self.engine.get_status(uid, STATUS.RESPAWN, STATUS_VALUE.DURATION)
            strs.append(SpriteLabel(
                Assets.get_sprite('ability', 'respawn'),
                f'* {format_time(duration)}s\n',
                (0,0,0,0.25),
            ))

        strs.append(SpriteLabel(
            Assets.get_sprite('ability', 'walk'),
            str(round(self.engine.s2ticks(self.engine.get_velocity(uid)))),
            (0,0,0,0),
        ))

        if self.engine.get_status(uid, STATUS.FOUNTAIN) > 0:
            strs.append(SpriteLabel(
                Assets.get_sprite('unit', 'fort'),
                '',
                (0,0,0,0),
            ))

        shop = self.engine.get_status(uid, STATUS.SHOP)
        if shop > 0:
            shop = list(ITEM_CATEGORIES)[round(shop)-1].name.lower().capitalize()
            strs.append(SpriteLabel(
                Assets.get_sprite('unit', 'basic-shop'),
                f'{shop}',
                (0,0,0,0.25),
            ))

        for stat, status in Mechanics.STATUSES.items():
            v = get(stat)
            if v > 0:
                name = stat.name.lower().capitalize()
                duration = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
                ds = f'* {format_time(duration)}s' if duration > 0 else ''
                strs.append(SpriteLabel(
                    Assets.get_sprite('ability', name),
                    # f'{round(v)}/{format_rp(v)}% {name}{ds}',
                    f'{ds}\n{round(v)}',
                    (0,0,0,0.25),
                ))

        return strs

    def hud_bars(self):
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

    def hud_click(self, hud, index, button):
        if button == 'left':
            if hud == 'left':
                aid = self.units[self.selected_unit].abilities[index]
                if aid is None:
                    return None
                ability = self.abilities[aid]
                color = modify_color(ability.color, v=0.3, a=0.85)
                stl = SpriteTitleLabel(
                    Assets.get_sprite('ability', ability.name), ability.name,
                    ability.description(self.engine, self.selected_unit), color)
                return stl
            elif hud == 'right':
                iid = self.engine.units[self.selected_unit].item_slots[index]
                if iid is None:
                    return
                item = ITEMS[iid]
                color = modify_color(item.color, v=0.3, a=0.85)
                text = item.shop_text(self.engine, 0)
                stl = SpriteTitleLabel(
                    Assets.get_sprite('ability', item.name), item.name, text, color)
                return stl
            elif hud == 'middle':
                stat = [
                    STAT.PHYSICAL, STAT.FIRE, STAT.EARTH,
                    STAT.AIR, STAT.WATER, STAT.GOLD,
                ][index]
                current = self.engine.get_stats(self.selected_unit, stat)
                delta = self.engine.get_stats(self.selected_unit, stat, value_name=VALUE.DELTA)
                dval = round(self.engine.s2ticks(delta)*60, 2)
                ds = ''
                if dval != 0:
                    ds = f'\n{nsign_str(dval)} /m'
                s = f'{current:.2f}{ds}'
                title = f'{stat.name.lower().capitalize()}'
                return SpriteTitleLabel(
                    STAT_SPRITES[index], title, f'{s}', (0,0,0,0.85))
        # Sorting, selling, etc. only relevant for player
        elif self.selected_unit == 0:
            if hud == 'left':
                if button == 'middle':
                    List.move_bottom(self.units[0].abilities, index)
                elif button == 'scrollup':
                    List.move_down(self.units[0].abilities, index)
                elif button == 'scrolldown':
                    List.move_up(self.units[0].abilities, index)
            if hud == 'right':
                if button == 'right':
                    self.itemsell(index, (0,0))
                elif button == 'middle':
                    List.move_bottom(self.units[0].item_slots, index)
                elif button == 'scrollup':
                    List.move_down(self.units[0].item_slots, index)
                elif button == 'scrolldown':
                    List.move_up(self.units[0].item_slots, index)

    # Browse
    def browse_main(self):
        item = ITEMS[self.shop_browse_item]
        return SpriteTitleLabel(
            Assets.get_sprite('ability', item.name),
            item.shop_name, item.shop_text(self.engine, 0),
            modify_color(item.color, a=0.5))

    def browse_elements(self):
        sts = []
        near_shop = self.engine.get_status(0, STATUS.SHOP) > 0
        for item in ITEMS:
            active = False
            if near_shop:
                r = item.check_buy(self.engine, 0)
                active = not isinstance(r, FAIL_RESULT)
            color = item.color
            v = 0
            a = 0.7
            s = str(round(item.cost))
            if active:
                a = 0.2
            final_color = modify_color(color, v=v, a=a)
            sts.append(SpriteLabel(
                Assets.get_sprite('ability', item.name),
                s, final_color))
        return sts

    def browse_click(self, index, button):
        if button == 'right':
            r = ITEMS[index].buy_item(self.engine, 0)
            if not isinstance(r, FAIL_RESULT):
                Assets.play_sfx('ability', 'shop', volume='feedback')
                return
            if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
                Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')
        if button == 'left':
            self.shop_browse_item = ITEMS[index].iid

    # Misc
    abilities = ABILITIES

    def update(self):
        if not self.enc_over:
            self.engine.update()

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

        rp_table = njoin([
            make_title('Score', length=30),
            f'Draft cost: {self.draft_cost}',
            f'Score: {self.score}',
            make_title('Reduction Points (RP) Table', length=30),
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

        text_unit = '\n'.join([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            make_title(f'Stat', length=30),
            f'{self.pretty_stats(uid)}',
            make_title(f'Status', length=30),
            f'{self.pretty_statuses(uid)}',
            make_title(f'Cooldown', length=30),
            f'{self.pretty_cooldowns(uid)}',
        ])

        text_unit2 = '\n'.join([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            make_title(f'Abilities', length=30),
            *(str(_) for _ in unit.abilities),
            make_title(f'Items', length=30),
            *(str(_) for _ in unit.item_slots),
            make_title(f'Debug', length=30),
            f'{unit.debug_str}',
            f'Action phase: {unit.uid % self.engine.AGENCY_PHASE_COUNT}',
            f'Agency: {self.engine.timers["agency"][unit.uid].mean_elapsed_ms:.3f} ms',
            f'Distance to player: {self.engine.unit_distance(0, uid):.1f}',
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
        return rp_table, text_unit, text_unit2, text_performance

    def __init__(self, game, player_abilities):
        self.dev_mode = Settings.get_setting('dev_build', 'General')
        self.show_debug = False
        self.shop_browse_item = ITEMS[0].iid
        self.game = game
        self.engine = EncounterEngine(self)
        self.map = MapGenerator(self)
        self.draft_cost = sum(ABILITIES[_].draft_cost for _ in player_abilities if _ is not None)
        self.engine.units[0].abilities = player_abilities
        # Setup units
        for unit in self.engine.units:
            unit.action_phase()
        Assets.play_sfx('ui', 'play', volume=Settings.get_volume('feedback'))

    def leave(self):
        self.enc_over = True

    @property
    def score(self):
        score = 0
        if self.win or not self.enc_over:
            elapsed_minutes = self.engine.tick/6000
            score = self.game.calc_score(self.draft_cost, elapsed_minutes)
        return score

    def debug(self, *args, dev_mode=-1, tick=None, tps=None, test=None, **kwargs):
        logger.debug(f'Logic Debug called (extra args: {args} {kwargs})')
        self.engine.set_tps(tps)
        if dev_mode == -1:
            dev_mode = self.dev_mode
        elif dev_mode == None:
            dev_mode = not self.dev_mode
        self.dev_mode = dev_mode
        if tick is not None:
            self.engine._do_ticks(tick)
        if test is not None:
            pass


FAIL_SFX = {
    FAIL_RESULT.INACTIVE: 'pause',
    FAIL_RESULT.MISSING_TARGET: 'target',
    FAIL_RESULT.MISSING_COST: 'cost',
    FAIL_RESULT.OUT_OF_BOUNDS: 'range',
    FAIL_RESULT.OUT_OF_RANGE: 'range',
    FAIL_RESULT.ON_COOLDOWN: 'cooldown',
}
