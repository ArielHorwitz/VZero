import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math
import numpy as np
from collections import defaultdict

from nutil.vars import NP, nsign_str
from nutil.random import SEED
from nutil.display import njoin, make_title
from nutil.time import RateCounter, ping, pong
from nutil.vars import modify_color, List

from data import resource_name
from data.load import RDF
from data.settings import Settings
from data.assets import Assets
from gui.api import SpriteTitleLabel, ProgressBar, SpriteBox, SpriteLabel

from engine.common import *
from engine.api import EncounterAPI as BaseEncounterAPI
from engine.encounter import Encounter as EncounterEngine

from logic.data import ABILITIES, METAGAME_BALANCE_SHORT
from logic.mechanics import Mechanics
from logic.mapgen import MapGenerator
from logic.items import ITEM, ITEMS, ITEM_CATEGORIES, Item


RNG = np.random.default_rng()
STAT_SPRITES = tuple([Assets.get_sprite('ability', s) for s in (
    'physical', 'fire', 'earth',
    'air', 'water', 'gold',
    'respawn', 'walk')]+[Assets.get_sprite('ui', 'crosshair3')])
SHOP_STATE_KEY = defaultdict(lambda: 0.7, {
    True: 1,
    FAIL_RESULT.MISSING_COST: 0.45,
    FAIL_RESULT.MISSING_TARGET: 0.2,
    FAIL_RESULT.OUT_OF_RANGE: 1,
    FAIL_RESULT.ON_COOLDOWN: 0,
})


FAIL_SFX_INTERVAL = Settings.get_setting('feedback_sfx_cooldown', 'UI')


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

    ouch_feedback = [
        (0, 'ouch', COLOR.RED),
        (1, 'ouch2', COLOR.BLUE),
    ]

    # GUI handlers
    @property
    def menu_text(self):
        if self.enc_over:
            if self.win:
                return f'You win!\nScore: {self.score}'
            else:
                return f'You lose :(\nScore: {self.score}'
        return f'Paused'

    def top_panel_labels(self):
        dstr = self.units[0].networth_str
        if self.dev_mode:
            dstr = " / ".join(str(round(_, 1)) for _ in self.engine.get_position(0)/100)
            dstr = f'DEBUG MODE - {dstr}'
        paused_str = '' if self.engine.auto_tick else 'Paused'
        view_size = '×'.join(str(round(_)) for _ in np.array(self.gui_size) * self.upp)
        vstr = f'{view_size} ({round(100 / self.upp)}% zoom)'
        return [
            f'Balance: {METAGAME_BALANCE_SHORT} | Score: {self.score}',
            dstr,
            f'{paused_str}\n{self.time_str}',
            vstr,
        ]

    @property
    def top_panel_color(self):
        return (1,1,1,1) if not self.dev_mode else (0.5,0,1,1)

    @property
    def control_buttons(self):
        return ['Pause' if self.engine.auto_tick else 'Play', 'Shop']

    def control_button_click(self, index):
        if index == 0:
            self.toggle_play()
            self.raise_gui_flag('browse_dismiss')
            self.raise_gui_flag('menu_dismiss' if self.engine.auto_tick else 'menu')
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
            if pong(self.__last_fail_sfx_ping) > FAIL_SFX_INTERVAL:
                Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')
                self.__last_fail_sfx_ping = ping()
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
            if pong(self.__last_fail_sfx_ping) > FAIL_SFX_INTERVAL:
                Assets.play_sfx('ui', FAIL_SFX[r], volume='feedback')
                self.__last_fail_sfx_ping = ping()
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
            Assets.play_sfx('ui', FAIL_SFX[r])
        else:
            Assets.play_sfx('ui', 'shop')

    def user_hotkey(self, hotkey, target):
        zoom_scale = 1.15
        if hotkey == 'toggle_play':
            self.toggle_play()
        elif hotkey == 'toggle_map':
            self.map_mode = not self.map_mode
            self.view_offset = None
        elif hotkey == 'zoom_in':
            self.zoom_in()
        elif hotkey == 'zoom_out':
            self.zoom_out()
        elif hotkey.startswith('pan_'):
            self.pan(d=hotkey[4:])
        elif hotkey == 'reset_view':
            self.map_mode = False
            self.view_offset = None
            self.set_zoom()
        elif hotkey == 'dev1':
            self.debug(dev_mode=None, test=True)
            self.map.refresh()
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
                self.raise_gui_flag('browse_dismiss')
                self.raise_gui_flag('menu_dismiss' if self.engine.auto_tick else 'menu')
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
    def sprite_bar_color(self, uid):
        allegiance = self.engine.get_stats(uid, STAT.ALLEGIANCE)
        if allegiance == 0:
            return (0, 0.7, 0, 1), (0, 0.25, 1, 1)
        elif allegiance < 0:
            return (0.8, 0.5, 0.2, 1), (0, 0.25, 1, 1)
        else:
            return (1, 0, 0, 1), (0, 0.25, 1, 1)

    def sprite_visible_mask(self):
        max_los = self.player_los
        if self.dev_mode:
            max_los = max(max_los, np.linalg.norm(self.view_size) / 2)
        in_los = self.engine.unit_distance(0) <= max_los
        is_ally = self.engine.get_stats(slice(None), STAT.ALLEGIANCE) == self.engine.get_stats(0, STAT.ALLEGIANCE)
        return in_los | is_ally | self.always_visible

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
                sls.append(SpriteBox(str(Assets.get_sprite('ui', 'blank')), '', (0,0,0,0), (1,1,1,1)))
                continue
            ability = self.abilities[aid]
            s, color = ability.gui_state(self.engine, uid)
            sls.append(SpriteBox(ability.sprite, s, modify_color(color, a=1), (1,1,1,1)))
        return sls

    def hud_right(self):
        uid = self.selected_unit
        sls = []
        for iid in self.units[uid].item_slots:
            if iid is None:
                sls.append(SpriteBox(Assets.get_sprite('ui', 'blank'), '', (0,0,0,0), (1,1,1,1)))
                continue
            item = ITEMS[iid]
            s, color = item.gui_state(self.engine, uid)
            sls.append(SpriteBox(item.sprite, s, modify_color(color, a=1), (1,1,1,1)))
        return sls

    def hud_middle_label(self):
        uid = self.selected_unit
        if self.dev_mode:
            return self.units[uid].debug_str
        else:
            return self.units[uid].say

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
            f'{round(self.engine.s2ticks(self.engine.get_velocity(uid)))}',
            f'{round(self.engine.get_stats(uid, STAT.HITBOX))}',
        ])
        return tuple(SpriteLabel(
            STAT_SPRITES[i], current[i],
            None) for i in range(9))

    def hud_statuses(self):
        def get(s):
            return Mechanics.get_status(self.engine, uid, s)
        def format_time(t):
            return math.ceil(self.engine.ticks2s(t))
        def format_rp(v):
            return round((1-Mechanics.rp2reduction(v))*100)

        uid = self.selected_unit
        self.__last_hud_statuses = []
        strs = []
        respawn = self.engine.get_status(uid, STATUS.RESPAWN)
        if respawn > 0:
            duration = self.engine.get_status(uid, STATUS.RESPAWN, STATUS_VALUE.DURATION)
            strs.append(SpriteBox(
                Assets.get_sprite('ability', 'respawn'),
                f'\n{format_time(duration)}s',
                (0,0,0,0), (0,0,0,0),
            ))
            self.__last_hud_statuses.append(STATUS.RESPAWN)

        if self.engine.get_status(uid, STATUS.FOUNTAIN) > 0:
            strs.append(SpriteBox(
                Assets.get_sprite('unit', 'fort'), '',
                (0,0,0,0), (0,0,0,0),
            ))
            self.__last_hud_statuses.append('fountain')

        shop_status = self.engine.get_status(uid, STATUS.SHOP)
        if shop_status > 0:
            shop_name, shop_color = Item.item_category_gui(shop_status)
            strs.append(SpriteBox(
                Assets.get_sprite('unit', f'{shop_name}-shop'), f'{shop_name}',
                (0,0,0,0), (0,0,0,0),
            ))
            self.__last_hud_statuses.append(STATUS.SHOP)

        for stat, status in Mechanics.STATUSES.items():
            v = get(stat)
            if v > 0:
                name = stat.name.lower().capitalize()
                duration = self.engine.get_status(uid, status, STATUS_VALUE.DURATION)
                ds = f'* {format_time(duration)}s' if duration > 0 else ''
                strs.append(SpriteBox(
                    Assets.get_sprite('ability', name), f'{ds}\n{round(v)}',
                    (0,0,0,0), (0,0,0,0),
                ))
                self.__last_hud_statuses.append(stat)

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
        bar_colors = self.sprite_bar_color(uid)
        return [
            ProgressBar(hp/max_hp, f'HP: {hp:.1f}/{max_hp:.1f} {delta_hp}', bar_colors[0]),
            ProgressBar(mana/max_mana, f'Mana: {mana:.1f}/{max_mana:.1f} {delta_mana}', bar_colors[1]),
        ]

    def hud_drag_drop(self, hud, origin, target, button):
        if self.selected_unit == 0 and button == 'middle' and origin != target:
            if hud == 'left':
                List.swap(self.units[0].abilities, origin, target)
                Assets.play_sfx('ui', 'select')
            if hud == 'right':
                List.swap(self.units[0].item_slots, origin, target)
                Assets.play_sfx('ui', 'select')

    def hud_click(self, hud, index, button):
        if button == 'left':
            if hud == 'left':
                aid = self.units[self.selected_unit].abilities[index]
                if aid is None:
                    return None
                ability = self.abilities[aid]
                stl = SpriteTitleLabel(
                    ability.sprite, ability.name,
                    ability.description(self.engine, self.selected_unit), None)
                return stl
            elif hud == 'right':
                iid = self.engine.units[self.selected_unit].item_slots[index]
                if iid is None:
                    return
                item = ITEMS[iid]
                text = item.shop_text(self.engine, 0)
                stl = SpriteTitleLabel(
                    Assets.get_sprite('ability', item.name), item.shop_name, text, None)
                return stl
            elif hud == 'middle':
                if index < 6:
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
                elif index == 6:
                    title = f'Respawn timer'
                    s = 'New respawn time in seconds'
                elif index == 7:
                    title = f'Movement Speed'
                    s = 'Current movement speed'
                elif index == 8:
                    title = 'Hitbox radius'
                    s = 'Radius of hitbox'
                else:
                    return None
                return SpriteTitleLabel(STAT_SPRITES[index], title, f'{s}', None)
            elif hud == 'status':
                return self.hud_status_tooltip(index)
        elif button == 'right':
            if self.selected_unit == 0 and hud == 'right':
                self.itemsell(index, (0,0))

    def hud_portrait_click(self):
        return SpriteTitleLabel(
            str(Assets.FALLBACK_SPRITE), 'RP Table',
            '\n'.join([f'{_}: {(1-Mechanics.rp2reduction(_))*100:.1f}% [b]/[/b] {Mechanics.rp2reduction(_)*100:.1f}%' for _ in (5,10,15,20,25,30,40,50,60,70,85,100,150,200,400)]),
            None)

    def hud_status_tooltip(self, index):
        status = self.__last_hud_statuses[index]
        sprite = str(Assets.FALLBACK_SPRITE)
        title = 'Unknown status'
        label = 'Missing tooltip'
        if status is STATUS.RESPAWN:
            sprite = Assets.get_sprite('ability', 'respawn')
            title = 'Respawn timer'
            label = 'Respawn time in seconds'
        if status is STATUS.SHOP:
            shop_name, shop_color = Item.item_category_gui(self.engine.get_status(self.selected_unit, STATUS.SHOP))
            sprite = Assets.get_sprite('unit', f'{shop_name}-shop')
            title = f'{shop_name} shop'
            label = f'Near {shop_name.lower()} shop'
            self.raise_gui_flag('browse')
            return None
        elif isinstance(status, STAT):
            sprite = Assets.get_sprite('ability', status.name)
            title = status.name.lower().capitalize()
            v = Mechanics.get_status(self.engine, self.selected_unit, status)
            sp = Mechanics.rp2reduction(v)
            if status is STAT.SLOW:
                label = f'Slowed by {int((1-sp)*100)}%'
            if status is STAT.SPIKES:
                label = f'Returns {round(v)} pure damage when hit by normal damage'
            if status is STAT.ARMOR:
                label = f'Reducing normal damage by {int((1-sp)*100)}%'
            if status is STAT.LIFESTEAL:
                label = f'Lifestealing {int(v)}% of outgoing normal damage'
            if status is STAT.BOUNDED:
                label = f'Prevented from moving or teleporting'
            if status is STAT.CUTS:
                label = f'Taking extra {round(v)} normal damage per hit'
            if status is STAT.VANITY:
                label = f'Incoming blast damage amplified by {int(v)}%'
            if status is STAT.REFLECT:
                label = f'Reflecting {int(v)}% of incoming blast damage as pure damage'
            if status is STAT.SENSITIVITY:
                sp = int(100 * Mechanics.scaling(v, 100, ascending=True))
                label = f'Amplifying incoming and outgoing status effects by {sp}%'
        elif status == 'fountain':
            sprite = Assets.get_sprite('unit', 'fort')
            title = 'Fountain healing'
            label = 'Healing from a fountain'
        return SpriteTitleLabel(sprite, title, label, None)

    # Browse
    def browse_main(self):
        shop_status = self.engine.get_status(0, STATUS.SHOP)
        if shop_status != 0:
            shop_name, shop_color = Item.item_category_gui(shop_status)
            shop_name = f'{shop_name} Shop'
            gold_count = int(self.engine.get_stats(0, STAT.GOLD))
            if self.units[0].empty_item_slots == 0:
                shop_color = (0,0,0,1)
                warning = 'Missing slots!'
            else:
                warning = ''
            main_text = '\n'.join([
                f'Welcome to the {shop_name}',
                f'',
                f'{warning}',
                f'You have: {gold_count} gold',
                f'',
                f'Legend:',
                f'White: for sale',
                f'Grey: missing gold/slots',
                f'Black: already owned',
                f'Color: for sale at another shop',
                f'',
                f'Refund policy:',
                f'80% refund on used items',
                f'100% refund on new items (<10 seconds)',
            ])
        else:
            shop_name = 'Out of shop range'
            shop_color = (0.25,0.25,0.25,1)
            map_hotkey = Settings.get_setting('toggle_map', 'Hotkeys')
            main_text = '\n'.join([
                f'Press {map_hotkey} to find a shop',
                *(f'{_+1}. {n.name.lower().capitalize()} shop' for _, n in enumerate(ITEM_CATEGORIES)),
            ])
        return SpriteTitleLabel(
            Assets.get_sprite('unit', f'{shop_name}-shop'),
            shop_name, main_text,
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

    def browse_click(self, index, button):
        if button == 'right':
            r = ITEMS[index].buy_item(self.engine, 0)
            if not isinstance(r, FAIL_RESULT):
                Assets.play_sfx('ui', 'shop')
                return
            if isinstance(r, FAIL_RESULT) and r in FAIL_SFX:
                Assets.play_sfx('ui', FAIL_SFX[r])
        if button == 'left':
            item = ITEMS[index]
            return SpriteTitleLabel(
                Assets.get_sprite('ability', item.name),
                item.shop_name, item.shop_text(self.engine, 0),
                None)

    # Misc
    abilities = ABILITIES

    def update(self, *a, **k):
        super().update(*a, **k)
        if not self.enc_over:
            PLAYER_ACTION_RADIUS = 3000
            in_action_radius = self.engine.get_distances(self.engine.get_position(0)) < PLAYER_ACTION_RADIUS
            active_uids = self.always_active | in_action_radius
            self.engine.update(active_uids)

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

    def __init__(self, game, player_abilities, draft_cost):
        self.dev_mode = Settings.get_setting('dev_build', 'General')
        self.show_debug = False
        self.game = game
        self.engine = EncounterEngine(self)
        self.map = MapGenerator(self)
        self.draft_cost = draft_cost
        self.engine.units[0].abilities = player_abilities
        self.always_visible = np.zeros(len(self.engine.units), dtype=np.bool)
        self.always_active = np.zeros(len(self.engine.units), dtype=np.bool)
        self.__last_hud_statuses = []
        self.__last_fail_sfx_ping = ping()
        self.map_mode = False
        self.set_zoom()
        # Setup units
        for unit in self.engine.units:
            unit.action_phase()
            self.always_visible[unit.uid] = unit.always_visible
            self.always_active[unit.uid] = unit.always_active

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
    FAIL_RESULT.INACTIVE: 'target',
    FAIL_RESULT.MISSING_TARGET: 'target',
    FAIL_RESULT.MISSING_COST: 'cost',
    FAIL_RESULT.OUT_OF_BOUNDS: 'target',
    FAIL_RESULT.OUT_OF_RANGE: 'range',
    FAIL_RESULT.OUT_OF_ORDER: 'target',
    FAIL_RESULT.ON_COOLDOWN: 'cooldown',
}
