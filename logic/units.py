import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from collections import defaultdict
import math
import numpy as np
import copy, random
from nutil.vars import normalize, collide_point, is_iterable, List, nsign_str, nsign, FIFO
from nutil.display import make_title
from nutil.time import ratecounter
from nutil.random import SEED
from data import DEV_BUILD
from data.load import RDF
from data.assets import Assets
from data.settings import PROFILE

from logic.common import *
from logic.mechanics import Mechanics
from logic.abilities import ABILITIES
from logic.items import ITEMS, ITEM_CATEGORIES
RNG = np.random.default_rng()


STARTING_PLAYER_STOCKS = 10
GRAVEYARD_POSITION = np.array([-1_000_000, -1_000_000], dtype=np.float64)


class Slots:
    def __init__(self, max_slots):
        self.max_slots = max_slots
        self.slots = [None for i in range(self.max_slots)]
        self.unslotted = set()
        self.all_elements = set()
        self.empty_slot = 0
        self.clear()

    def __repr__(self):
        return f'<Slots {self.slots} | {self.unslotted}>'

    def swap_slots(self, i1, i2):
        List.swap(self.slots, i1, i2)
        self.refresh()

    def clear(self):
        self.slots = [None for i in range(self.max_slots)]
        self.unslotted = set()
        self.elements = set()
        self.empty_slot = 0

    def refresh(self):
        self.all_elements = set(self.slots) | self.unslotted
        if None in self.all_elements:
            self.all_elements.remove(None)
        for i, e in enumerate(self.slots):
            if e is None:
                self.empty_slot = i
                break
        else:
            self.empty_slot = None

    def add_prefer_slot(self, e, slot):
        if self.slots[slot] is None:
            self.add_slotted(e, slot)
        else:
            self.add(e)

    def add(self, e):
        es = [e] if not is_iterable(e) else e
        for e in es:
            if self.empty_slot is None:
                self.add_unslotted(e)
            else:
                self.add_slotted(e)

    def add_slotted(self, e, slot=None):
        if slot is None:
            slot = self.empty_slot
        assert slot is not None
        assert self.slots[slot] is None
        self.slots[slot] = e
        self.refresh()
        return slot

    def add_unslotted(self, e):
        assert e not in self.unslotted
        self.unslotted.add(e)
        self.refresh()

    def remove(self, e):
        if e in self.slots:
            i = self.slots.index(e)
            self.slots[i] = None
        elif e in self.unslotted:
            self.unslotted.remove(e)
        else:
            raise ValueError(f'Requested remove {e} from {self} but not found: {self.slots} {self.unslotted}')
        self.refresh()


class Unit:
    _respawn_timer = 12000  # ~ 2 minutes
    say = ''
    win_on_death = False
    lose_on_death = False

    @staticmethod
    def _get_default_stats():
        table = np.zeros(shape=(len(STAT), len(VALUE)))
        LARGE_ENOUGH = 1_000_000_000
        table[:, VALUE.CURRENT] = 0
        table[:, VALUE.DELTA] = 0
        table[:, VALUE.TARGET] = -LARGE_ENOUGH
        table[:, VALUE.MIN] = 0
        table[:, VALUE.MAX] = LARGE_ENOUGH

        table[STAT.STOCKS, VALUE.MIN] = -LARGE_ENOUGH
        table[STAT.ALLEGIANCE, VALUE.MIN] = -LARGE_ENOUGH
        table[STAT.ALLEGIANCE, VALUE.CURRENT] = 1
        table[(STAT.POS_X, STAT.POS_Y), VALUE.MIN] = -LARGE_ENOUGH
        table[STAT.WEIGHT, VALUE.MIN] = -1
        table[STAT.HITBOX, VALUE.CURRENT] = 100
        table[STAT.MOVESPEED, VALUE.CURRENT] = 20
        table[STAT.MOVESPEED, VALUE.MIN] = 5
        table[STAT.LOS, VALUE.CURRENT] = 1000
        table[STAT.HP, VALUE.CURRENT] = LARGE_ENOUGH
        table[STAT.HP, VALUE.TARGET] = 0
        table[STAT.MANA, VALUE.CURRENT] = LARGE_ENOUGH
        table[STAT.MANA, VALUE.MAX] = 20

        ELEMENTAL_STATS = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.AIR, STAT.WATER]
        table[ELEMENTAL_STATS, VALUE.CURRENT] = 1
        table[ELEMENTAL_STATS, VALUE.MIN] = 1
        return table

    @classmethod
    def _load_raw_stats(cls, raw_stats):
        stats = cls._get_default_stats()
        modified_stats = []
        for raw_key, raw_value in raw_stats.items():
            stat, value = str2statvalue(raw_key)
            stats[stat][value] = float(raw_value)
            modified_stats.append(f'{stat.name}.{value.name}: {raw_value}')
        # logger.debug(f'Loaded raw stats: {", ".join(modified_stats)}')
        return stats

    @classmethod
    def from_data(cls, api, uid, unit_name):
        raw_data = copy.deepcopy(RAW_UNITS[internal_name(unit_name)])
        unit_cls = UNIT_CLASSES[raw_data.default['type']]
        return unit_cls(api, uid, unit_name, raw_data)

    def __init__(self, api, uid, name, raw_data):
        self.__uid = uid
        self._raw_data = raw_data
        self.p = raw_data.default
        raw_stats = raw_data['stats'] if 'stats' in raw_data else {}
        self.starting_stats = self._load_raw_stats(raw_stats)
        self.grave_offset = np.array([(self.uid%10)*300, (self.uid//10)*300], dtype=np.float64)
        self.grave_pos = GRAVEYARD_POSITION + self.grave_offset
        self.cache = defaultdict(lambda: None)
        self.always_visible = True if 'always_visible' in self.p.positional else False
        self.always_active = True if 'always_active' in self.p.positional else False
        self.death_sfx = raw_data.default['death_sfx'] if 'death_sfx' in raw_data.default else f'ui.death-unit{RNG.integers(4)+1}'
        self.respawn_sfx = f'ui.{raw_data.default["respawn_sfx"]}' if 'respawn_sfx' in raw_data.default else 'ui.respawn-unit'
        self.api = api
        self.engine = api.engine
        self.name = raw_data.default['name'] if 'name' in raw_data.default else name
        sprite_name = raw_data.default['sprite'] if 'sprite' in raw_data.default else name
        self.sprite = Assets.get_sprite(f'units.{sprite_name}')
        self.regen_trackers = defaultdict(lambda: FIFO(int(FPS*2)))
        # Abilities
        self._ability_slots = Slots(8)
        self._item_slots = Slots(8)
        self.__item_aids = set()
        self.off_cooldown_aids = defaultdict(set)
        self.builtin_walk = str2ability('Builtin Walk')
        self.builtin_loot = str2ability('Builtin Loot')
        self.default_abilities = []
        if 'abilities' in self.p:
            self.default_abilities = [str2ability(a) for a in self.p['abilities'].split(', ')]

        logger.info(f'Created unit: {name} with data: {self._raw_data}')

    @property
    def uid(self):
        return self.__uid

    def swap_ability_slots(self, i1, i2):
        self._ability_slots.swap_slots(i1, i2)

    def swap_item_slots(self, i1, i2):
        self._item_slots.swap_slots(i1, i2)

    def add_item(self, iid):
        self._item_slots.add_slotted(iid)
        item = ITEMS[iid]
        if item.aid:
            self.__item_aids.add(item.aid)
            self._load_ability(item.aid)

    def remove_item(self, iid):
        self._item_slots.remove(iid)
        item = ITEMS[iid]
        if item.aid:
            self.__item_aids.remove(item.aid)
            self._unload_ability(item.aid)

    def _load_ability(self, aid):
        if aid is None:
            return
        ability = self.api.abilities[aid]
        self.off_cooldown_aids[ability.off_cooldown_aid].add(aid)
        ability.load_on_unit(self.engine, self.uid)

    def _unload_ability(self, aid):
        if aid is None:
            return
        ability = self.api.abilities[aid]
        self.off_cooldown_aids[ability.off_cooldown_aid].remove(aid)
        ability.unload_from_unit(self.engine, self.uid)

    def set_abilities(self, abilities):
        # TODO make move slotted to unslotted
        for i, aid in enumerate(abilities):
            self._ability_slots.add_prefer_slot(aid, i)
            self._load_ability(aid)

    @property
    def unslotted_abilities(self):
        return (self.abilities | self.item_abilities) - set(self.ability_slots) - set(self.item_slots)

    @property
    def item_abilities(self):
        return self.__item_aids

    @property
    def items(self):
        return self._item_slots.all_elements

    @property
    def item_slots(self):
        return self._item_slots.slots

    @property
    def abilities(self):
        return self._ability_slots.all_elements

    @property
    def ability_slots(self):
        return self._ability_slots.slots

    @property
    def draft_cost(self):
        nones = self.ability_slots.count(None)
        if nones >= 8:
            return 0
        return round(sum([ABILITIES[a].draft_cost for a in self.ability_slots if a is not None]) / (8-nones))

    def set_spawn_location(self, spawn):
        self.starting_stats[(STAT.POS_X, STAT.POS_Y), VALUE.CURRENT] = spawn
        self.starting_stats[(STAT.POS_X, STAT.POS_Y), VALUE.TARGET] = spawn

    @property
    def total_networth(self):
        nw = self.engine.get_stats(self.uid, STAT.GOLD)
        for iid in set(self.item_slots):
            if iid is None:
                continue
            nw += ITEMS[iid].cost
        return nw

    def use_item_slot(self, index, target, alt=0):
        iid = self.item_slots[index]
        if iid is not None:
            self.use_item(iid, target, alt)

    def use_item(self, iid, target, alt=0):
        if iid not in self.items:
            logger.warning(f'{self} using item {repr(iid)} not in items: {self.items}')
        if not self.engine.auto_tick and not self.api.debug_mode:
            logger.warning(f'{self} tried using item {iid.name} while paused')
            self.api.play_feedback(FAIL_RESULT.INACTIVE, self.uid)
            return
        if not self.is_alive:
            logger.warning(f'{self} is dead and requested item {iid.name}')
            self.api.play_feedback(FAIL_RESULT.INACTIVE, self.uid)
            return

        item = ITEMS[iid]
        item.active(self.api, self.uid, target, alt)

    def buy_item(self, iid):
        r = ITEMS[iid].buy_item(self.engine, self.uid)
        self.api.play_feedback(r if isinstance(r, FAIL_RESULT) else 'shop', self.uid)

    def sell_item(self, item_index):
        iid = self.item_slots[item_index]
        if iid is None:
            return
        item = ITEMS[iid]
        r = item.sell_item(self.engine, self.uid)
        self.api.play_feedback(r if isinstance(r, FAIL_RESULT) else 'shop', self.uid)
        self.check_win_condition()

    def use_ability_slot(self, index, target, alt=0):
        aid = self.ability_slots[index]
        if aid is not None:
            self.use_ability(aid, target, alt)

    def use_ability(self, aid, target, alt=0):
        if aid not in self.abilities:
            logger.warning(f'{self} using ability {repr(aid)} not in abilities: {self.abilities}')
        if not self.engine.auto_tick and not self.api.debug_mode:
            logger.warning(f'{self} tried using ability {aid.name} while paused')
            self.api.play_feedback(FAIL_RESULT.INACTIVE, self.uid)
            return
        if not self.is_alive:
            logger.warning(f'{self} is dead and requested ability {aid.name}')
            self.api.play_feedback(FAIL_RESULT.INACTIVE, self.uid)
            return

        ability = self.api.abilities[aid]
        ability.active(self.engine, self.uid, target, alt)

    def use_walk(self, target):
        self.use_ability(self.builtin_walk, target)

    def use_loot(self, target):
        self.use_ability(self.builtin_loot, target)

    def setup(self):
        self.spawn_pos = self.engine.get_position(self.uid)
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self.set_abilities(self.default_abilities)
        self._ability_slots.add_unslotted(self.builtin_walk)
        self._load_ability(self.builtin_walk)
        self._ability_slots.add_unslotted(self.builtin_loot)
        self._load_ability(self.builtin_loot)
        self._setup()

    def action_phase(self):
        pass

    def passive_phase(self):
        paids = set(self.abilities) | set(ITEMS[iid].aid for iid in self.items) - {None}
        for paid in paids:
            ABILITIES[paid].passive(self.engine, self.uid, self.engine.AGENCY_PHASE_COUNT)

    def off_cooldown(self, aid):
        if not self.is_alive:
            return
        for paid in self.off_cooldown_aids[aid]:
            self.api.abilities[paid].off_cooldown(self.engine, self.uid)

    @property
    def size(self):
        hb = self.engine.get_stats(self.uid, STAT.HITBOX)
        return np.array([hb, hb])*2

    @property
    def is_alive(self):
        return self.engine.get_stats(self.uid, STAT.HP) > 0

    @property
    def allegiance(self):
        return self.engine.get_stats(self.uid, STAT.ALLEGIANCE)

    @property
    def empty_item_slots(self):
        return self.item_slots.count(None)

    @property
    def position(self):
        return self.engine.get_position(self.uid)

    @property
    def view_distance(self):
        los = Mechanics.get_status(self.engine, self.uid, STAT.LOS)
        raw_darkness = Mechanics.get_status(self.engine, self.uid, STAT.DARKNESS)
        darkness = Mechanics.scaling(raw_darkness)
        return round(los * darkness)

    def _setup(self):
        pass

    def hp_zero(self):
        if self.engine.get_status(self.uid, STATUS.STOCKS) == 0:
            self.engine.set_stats(self.uid, STAT.STOCKS, -1, additive=True)
        self.engine.set_status(self.uid, STATUS.STOCKS, 0, 0)
        logger.info(f'{self} died. Remaining stocks: {self.stocks}')
        self.play_death_sfx()
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self.engine.set_status(self.uid, STATUS.RESPAWN, self._respawn_timer, 1)
        self.check_win_condition()

    def play_death_sfx(self):
        Assets.play_sfx(self.death_sfx, volume='monster_death')

    def play_respawn_sfx(self):
        Assets.play_sfx(self.respawn_sfx, volume='feedback')

    def status_zero(self, status):
        logger.debug(f'{self} lost status: {status.name}.')
        if status is STATUS.RESPAWN:
            self.respawn()
        elif status is STATUS.SLOW:
            Mechanics.apply_walk(self.engine, Mechanics.mask(self.engine, self.uid))

    def respawn(self, reset_gold=True):
        logger.info(f'{self} respawned.')
        max_hp = self.engine.get_stats(self.uid, STAT.HP, VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.HP, max_hp)
        max_mana = self.engine.get_stats(self.uid, STAT.MANA, VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.MANA, max_mana)
        self.move_to_spawn()
        self.engine.kill_dmods(self.uid)
        self.engine.kill_statuses(self.uid)
        if reset_gold:
            self.engine.set_stats(self.uid, STAT.GOLD, self._respawn_gold)
        self.play_respawn_sfx()

    def move_to_spawn(self):
        self.engine.set_position(self.uid, self.spawn_pos)
        self.engine.set_position(self.uid, self.spawn_pos, value_name=VALUE.TARGET)

    def move_to_graveyard(self):
        self.engine.set_position(self.uid, self.grave_pos)
        self.engine.set_position(self.uid, self.grave_pos, value_name=VALUE.TARGET)

    @property
    def networth_str(self):
        nw = self.total_networth
        if nw > 10**3:
            nw = round(nw/1000, 1)
            k = 'k'
        else:
            nw = math.floor(nw)
            k = ''
        return f'Networth: Σ{nw}{k}'

    def debug_str(self, verbose=False):
        velocity = self.engine.get_velocity(self.uid)
        s = [
            f'Draft cost: {self.draft_cost}',
            f'Current velocity: {s2ticks(velocity):.2f}/s ({velocity:.2f}/t)',
            f'Action phase: {self.uid % self.api.engine.AGENCY_PHASE_COUNT}',
            f'Spawn location: {self.spawn_pos}',
            f'Grave offset: {self.grave_offset}',
            f'Agency: {self.api.engine.agency_timers[self.uid].mean_elapsed_ms:.3f} ms',
            f'Distance to player: {self.api.engine.unit_distance(0, self.uid):.1f}',
        ]
        if verbose:
            dmods = self.api.engine.get_dmod(self.uid)
            dmod_str = ', '.join([f'{STAT_LIST[i].name.lower()}: ' \
                f'{nsign_str(round(s2ticks(dmods[i]), 3))}' \
                for i in np.flatnonzero(dmods)])
            s.extend([
                f'Delta mods: {dmod_str}',
                make_title('Unit Cache:', length=30),
            ])
            for k, v in self.cache.items():
                if is_iterable(v):
                    if len(v) > 20:
                        v = np.flatnonzero(v)
                s.append(f'{k}: {str(v)}')
        return '\n'.join(s)

    def __repr__(self):
        return f'{self.name} #{self.uid}'

    def check_win_condition(self):
        pass

    @property
    def stocks(self):
        return round(Mechanics.get_status(self.engine, self.uid, STAT.STOCKS))


class Player(Unit):
    say = 'Let\'s defeat the boss!'

    def _setup(self):
        self.engine.set_stats(self.uid, STAT.STOCKS, STARTING_PLAYER_STOCKS)
        self._respawn_timer = 500
        self._respawn_timer_scaling = 100
        self.death_sfx = 'ui.death-player'
        self.respawn_sfx = 'ui.respawn-player'
        if not DEV_BUILD:  # PLAYER SETUP RESPAWN SFX
            self.play_respawn_sfx()

    def play_death_sfx(self):
        Assets.play_sfx(self.death_sfx, volume='feedback')

    def respawn(self):
        super().respawn(reset_gold=False)
        self._respawn_timer += self._respawn_timer_scaling

    def check_win_condition(self):
        if self.stocks <= 0:
            self.api.end_encounter(win=False)


class Creep(Unit):
    say = 'I\'m coming for that fort!'
    def _setup(self):
        self.respawn_sfx = 'ui.respawn-wave' if self.respawn_sfx == 'ui.respawn-unit' else self.respawn_sfx
        self.color = (1, 0, 0)
        self.wave_interval = int(float(self.p['wave']) * 100)
        self.wave_offset = int(float(self.p['wave_offset']) * 100)
        self.scaling = float(self.p['scaling']) if 'scaling' in self.p else 1
        # Space out the wave, as collision is finnicky at the time of writing
        self.spawn_pos += RNG.random(2) * self.engine.get_stats(self.uid, STAT.HITBOX) * 0.5
        # Prepare the first wave
        self.first_wave = True
        self.move_to_graveyard()
        self.engine.set_stats(self.uid, STAT.HP, 0)
        self.engine.set_status(self.uid, STATUS.RESPAWN, self._respawn_timer + 1, 1)

    @property
    def target(self):
        return self.engine.units[0].spawn_pos

    def respawn(self):
        super().respawn()
        if self.first_wave is False:
            self.scale_power()
        self.first_wave = False
        self.use_walk(self.target)

    def scale_power(self):
        currents = [STAT.PHYSICAL, STAT.FIRE, STAT.EARTH, STAT.WATER, STAT.GOLD]
        deltas = maxs = [STAT.HP, STAT.MANA]
        self.engine.set_stats(self.uid, currents, self.scaling, multiplicative=True)
        self.engine.set_stats(self.uid, deltas, self.scaling, value_name=VALUE.DELTA, multiplicative=True)
        self.engine.set_stats(self.uid, maxs, self.scaling, value_name=VALUE.MAX, multiplicative=True)
        self.engine.set_stats(self.uid, maxs, 1_000_000)

    @property
    def _respawn_timer(self):
        ticks_since_last_wave = (self.engine.tick - self.wave_offset) % self.wave_interval
        ticks_to_next_wave = self.wave_interval - ticks_since_last_wave
        return ticks_to_next_wave

    def action_phase(self):
        self.use_walk(self.target)
        for aid in self.ability_slots:
            if aid is None:
                continue
            self.use_ability(aid, None)

    def debug_str(self, *a, **k):
        return f'{super().debug_str(*a, **k)}\nSpawned at: {self.spawn_pos}\nNext wave: {self._respawn_timer}'


class Camper(Unit):
    say = '"Personal space... I need my personal space..."'
    def _setup(self):
        self.color = (1, 0, 0)
        if len(self.default_abilities) == 0:
            self.set_abilities([ABILITY.ATTACK])
        self.camp = self.engine.get_position(self.uid)
        self.__keep_distance = float(self.p['keep_distance']) if 'keep_distance' in self.p else 0
        self.__aggro_flank = float(self.p['aggro_flank']) * nsign(RNG.random()-0.5) if 'aggro_flank' in self.p else 0
        self.__aggro_range = float(self.p['aggro_range'])
        self.__aggro_range_camp = float(self.p['aggro_range_camp']) if 'aggro_range_camp' in self.p else self.__aggro_range
        self.__deaggro_range = float(self.p['deaggro_range'])
        self.__reaggro_range = float(self.p['reaggro_range'])
        self.__camp_spread = float(self.p['camp_spread'])
        self.__deaggro = False
        self.__walk_target = self.camp
        self.__next_walk = self.engine.tick

    def action_phase(self):
        distance_from_me = self.engine.unit_distance(self.uid, 0)
        visible_to_me = distance_from_me <= self.view_distance
        if visible_to_me:
            my_camp_dist = self.engine.get_distances(self.camp, self.uid)
            in_aggro_range_self = distance_from_me < self.__aggro_range
            in_aggro_range_camp = self.engine.get_distances(self.camp, 0)[0] < self.__aggro_range_camp
            in_aggro_range = in_aggro_range_self or in_aggro_range_camp
            if in_aggro_range and not self.__deaggro and self.engine.units[0].is_alive:
                player_pos = self.engine.get_position(0)
                if self.__aggro_flank != 0:
                    self.use_walk(self.flank_pos(0))
                elif self.__keep_distance > 0:
                    self.use_walk(self.straight_distance(0))
                else:
                    self.use_walk(player_pos)
                for aid in self.ability_slots:
                    if aid is None:
                        continue
                    self.use_ability(aid, player_pos)
                if my_camp_dist > self.__deaggro_range:
                    self.__deaggro = True
            else:
                if self.__deaggro is True and my_camp_dist < self.__reaggro_range:
                    self.__deaggro = False
                self.use_walk(self.walk_target)
        else:
            self.__deaggro = False
            self.use_walk(self.walk_target)

    def straight_distance(self, uid):
        my_pos = self.engine.get_position(self.uid)
        target_pos = self.engine.get_position(0)
        vector_from_target = my_pos - target_pos
        hb = Mechanics.get_stats(self.engine, uid, STAT.HITBOX) + Mechanics.get_stats(self.engine, self.uid, STAT.HITBOX)
        final_pos = target_pos + normalize(vector_from_target, hb+self.__keep_distance)
        return final_pos

    def flank_pos(self, uid):
        my_pos = self.engine.get_position(self.uid)
        target_pos = self.engine.get_position(0)
        target_vector = target_pos - my_pos
        flank_vector = self.rotate_vector(target_vector, self.__aggro_flank)
        hb = Mechanics.get_stats(self.engine, uid, STAT.HITBOX) + Mechanics.get_stats(self.engine, self.uid, STAT.HITBOX)
        flank_pos = target_pos + normalize(flank_vector, hb+self.__keep_distance)
        return flank_pos

    @staticmethod
    def rotate_vector(xy, radians=1.5):
        x, y = xy
        xx = x * math.cos(radians) + y * math.sin(radians)
        yy = -x * math.sin(radians) + y * math.cos(radians)
        return xx, yy

    @property
    def walk_target(self):
        if self.__next_walk <= self.engine.tick:
            self.__walk_target = self.camp+(RNG.random(2) * self.__camp_spread*2 - self.__camp_spread)
            self.__next_walk = self.engine.tick + SEED.r * 500
        return self.__walk_target

    def debug_str(self, *a, **k):
        return '\n'.join([
            f'{super().debug_str(*a, **k)}',
            f'Camping at: {pos2str(self.camp)}',
            f'Camp spread: {self.__camp_spread}',
            f'Next walk: {self.__next_walk}',
            f'Walk target: {pos2str(self.__walk_target)}',
            f'Keep distance: {self.__keep_distance}',
            f'Aggro flank: {self.__aggro_flank}',
            f'Aggro range: {self.__aggro_range}',
            f'Deaggro range: {self.__deaggro_range}',
            f'Reaggro range: {self.__reaggro_range}',
            f'Deaggro\'d: {self.__deaggro}',
        ])


class Boss(Camper):
    say = 'Foolishly brave are we?'

    def _setup(self):
        super()._setup()
        self.death_sfx = None

    def check_win_condition(self):
        if self.stocks <= 0:
            self.api.end_encounter(win=True)


class Treasure(Unit):
    say = 'Breach me if you can'
    def _setup(self):
        self._respawn_timer = 30000
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)


class Shopkeeper(Unit):
    say = 'Looking for wares?'
    def _setup(self):
        self.set_abilities([ABILITY.SHOPKEEPER])
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        category = 'BASIC' if 'category' not in self.p else self.p['category']
        icat = getattr(ITEM_CATEGORIES, category.upper())
        self.engine.set_stats(self.uid, STAT.SHOP, icat.value, value_name=VALUE.MIN)
        self.engine.set_stats(self.uid, STAT.SHOP, icat.value, value_name=VALUE.MAX)
        self.name = f'{category.lower().capitalize()} shop'


class Fountain(Unit):
    say = 'Bestowing life is a great pleasure'

    def _setup(self):
        self.set_abilities([ABILITY.FOUNTAIN_AURA])
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        self.death_sfx = None


class Fort(Fountain):
    say = 'If I fall, it is all for naught'
    def _setup(self):
        self.set_abilities([ABILITY.FORT_AURA])
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        self.death_sfx = None

    def check_win_condition(self):
        if self.stocks <= 0:
            self.api.end_encounter(win=False)


class DPSMeter(Unit):
    def _setup(self):
        self.engine.set_stats(self.uid, STAT.HP, 10**12, value_name=VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.HP, 10**12)
        self.engine.set_stats(self.uid, STAT.HP, 0, value_name=VALUE.DELTA)
        self.engine.set_stats(self.uid, STAT.MANA, 10**12, value_name=VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.MANA, 10**12)
        self.engine.set_stats(self.uid, STAT.MANA, 0, value_name=VALUE.DELTA)
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        self.__started = False
        self.__sample_size = 10
        self.__sample_index = 0
        self.__sample = np.zeros((self.__sample_size, 2), dtype = np.float64)
        self.__sample[0, 0] = 1
        self.__last_tick = self.engine.tick
        self.__last_hp = self.engine.get_stats(self.uid, STAT.HP)
        self.__tps = 100

    def action_phase(self):
        new_hp = self.engine.get_stats(self.uid, STAT.HP)
        self.__sample_index += 1
        self.__sample_index %= self.__sample_size
        sample_time = self.engine.tick - self.__last_tick
        self.__last_tick = self.engine.tick
        sample_damage = self.__last_hp - new_hp
        self.__last_hp = new_hp
        self.__sample[self.__sample_index] = (sample_time, sample_damage)

        total_time = self.__sample[:, 0].sum()
        total_damage = self.__sample[:, 1].sum()
        dps = total_damage / total_time
        self.say = f'DPS: {dps*self.__tps:.2f}'


UNIT_CLASSES = {
    'fort': Fort,
    'player': Player,
    'boss': Boss,
    'creep': Creep,
    'camper': Camper,
    'treasure': Treasure,
    'shopkeeper': Shopkeeper,
    'fountain': Fountain,
    'dps_meter': DPSMeter,
}


def _load_unit_types():
    all_raw_data = RDF.from_file(RDF.CONFIG_DIR / 'units.rdf', convert_float=True)
    units = {}
    for unit_name, raw_data in all_raw_data.items():
        iname = internal_name(unit_name)
        if iname in units:
            raise CorruptedDataError(f'Unit name duplication: {iname}')
        raw_data.default['name'] = unit_name
        units[iname] = raw_data
    logger.info(f'Loaded {len(units)} units.')
    return units


RAW_UNITS = _load_unit_types()
