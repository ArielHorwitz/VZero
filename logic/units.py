import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from collections import defaultdict
import math
import numpy as np
import copy, random
from nutil.vars import normalize, collide_point, is_iterable, List, nsign_str, FIFO
from nutil.display import make_title
from nutil.time import ratecounter
from nutil.random import SEED
from data.assets import Assets
from data.settings import Settings

from engine.common import *
from engine.unit import Unit as BaseUnit
from logic.data import RAW_UNITS, ABILITIES
from logic.items import ITEMS, ITEM_CATEGORIES
from logic.mechanics import Mechanics

RNG = np.random.default_rng()


class Slots:
    def __init__(self, max_slots):
        self.max_slots = max_slots
        self.slots = [None for i in range(self.max_slots)]
        self.unslotted = set()
        self.all_elements = set()
        self.empty_slot = 0
        self.clear()

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


class Unit(BaseUnit):
    _respawn_timer = 12000  # ~ 2 minutes
    say = ''

    @staticmethod
    def _get_default_stats():
        table = np.zeros(shape=(len(STAT), len(VALUE)))
        LARGE_ENOUGH = 1_000_000_000
        table[:, VALUE.CURRENT] = 0
        table[:, VALUE.DELTA] = 0
        table[:, VALUE.TARGET] = -LARGE_ENOUGH
        table[:, VALUE.MIN] = 0
        table[:, VALUE.MAX] = LARGE_ENOUGH

        table[STAT.ALLEGIANCE, VALUE.MIN] = -LARGE_ENOUGH
        table[STAT.ALLEGIANCE, VALUE.CURRENT] = 1
        table[(STAT.POS_X, STAT.POS_Y), VALUE.MIN] = -LARGE_ENOUGH
        table[STAT.WEIGHT, VALUE.MIN] = -1
        table[STAT.HITBOX, VALUE.CURRENT] = 100
        table[STAT.MOVESPEED, VALUE.CURRENT] = 10
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
        super().__init__(uid)
        self._raw_data = raw_data
        self.p = raw_data.default
        raw_stats = raw_data['stats'] if 'stats' in raw_data else {}
        self.starting_stats = self._load_raw_stats(raw_stats)
        self.cache = defaultdict(lambda: None)
        self.always_visible = True if 'always_visible' in self.p.positional else False
        self.always_active = True if 'always_active' in self.p.positional else False
        self.win_on_death = False
        self.lose_on_death = False
        self.api = api
        self.engine = api.engine
        self.name = self.__start_name = raw_data.default['name'] if 'name' in raw_data.default else name
        self.cooldown_aids = defaultdict(set)

        self._ability_slots = Slots(8)
        self._item_slots = Slots(8)
        self.__item_aids = set()

        self.regen_trackers = defaultdict(lambda: FIFO(int(FPS*2)))

        self.default_abilities = []
        if 'abilities' in self.p:
            self.default_abilities = [str2ability(a) for a in self.p['abilities'].split(', ')]

        logger.info(f'Created unit: {name} with data: {self._raw_data}')

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
        self.cooldown_aids[ability.off_cooldown_aid].add(aid)
        ability.load_on_unit(self.engine, self.uid)

    def _unload_ability(self, aid):
        if aid is None:
            return
        ability = self.api.abilities[aid]
        self.cooldown_aids[ability.off_cooldown_aid].remove(aid)
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
    def total_draft_cost(self):
        return sum([ABILITIES[a].draft_cost for a in self.ability_slots if a is not None])

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

    def use_item(self, iid, target, alt=0):
        with ratecounter(self.engine.timers['ability_single']):
            if iid not in self.items:
                logger.warning(f'{self} using item {repr(iid)} not in items: {self.items}')

            if not self.engine.auto_tick and not self.api.dev_mode:
                logger.warning(f'{self} tried using item {iid.name} while paused')
                return FAIL_RESULT.INACTIVE

            if not self.is_alive:
                logger.warning(f'{self} is dead and requested item {iid.name}')
                return FAIL_RESULT.MISSING_TARGET

            target = Mechanics.bound_to_map(self.api, target)

            item = ITEMS[iid]
            r = item.active(self.api, self.uid, target, alt)
            if r is None:
                m = f'Item {item} ability {item.ability.__class__}.active() method returned None. Must return FAIL_RESULT on fail or aid on success.'
                logger.warning(m)
            return r

    def use_ability(self, aid, target, alt=0):
        with ratecounter(self.engine.timers['ability_single']):
            if aid not in self.abilities:
                logger.warning(f'{self} using ability {repr(aid)} not in abilities: {self.abilities}')

            if not self.engine.auto_tick and not self.api.dev_mode:
                logger.warning(f'{self} tried using ability {aid.name} while paused')
                return FAIL_RESULT.INACTIVE

            if not self.is_alive:
                logger.warning(f'{self} is dead and requested ability {aid.name}')
                return FAIL_RESULT.MISSING_TARGET

            ability = self.api.abilities[aid]
            r = ability.active(self.engine, self.uid, target, alt)
            if r is None:
                m = f'Ability {ability.__class__}.active() method returned None. Must return FAIL_RESULT on fail or aid on success.'
                logger.warning(m)
            return r

    def setup(self):
        self._respawn_location = self.engine.get_position(self.uid)
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self.set_abilities(self.default_abilities)
        self._setup()

    def passive_phase(self):
        for aid in self.abilities:
            self.api.abilities[aid].passive(self.engine, self.uid, self.engine.AGENCY_PHASE_COUNT)
        for iid in self.items:
            ITEMS[iid].passive(self.engine, self.uid, self.engine.AGENCY_PHASE_COUNT)

    def off_cooldown(self, aid):
        if not self.is_alive:
            return
        for paid in self.cooldown_aids[aid]:
            self.api.abilities[paid].off_cooldown(self.engine, self.uid)

    @property
    def sprite(self):
        return Assets.get_sprite('unit', self.__start_name)

    @property
    def size(self):
        hb = self.engine.get_stats(self.uid, STAT.HITBOX)
        return np.array([hb, hb])*2

    @property
    def is_alive(self):
        return self.engine.get_stats(self.uid, STAT.HP) > 0

    @property
    def empty_item_slots(self):
        return self.item_slots.count(None)

    @property
    def view_distance(self):
        los = Mechanics.get_status(self.engine, self.uid, STAT.LOS)
        raw_darkness = Mechanics.get_status(self.engine, self.uid, STAT.DARKNESS)
        darkness = Mechanics.scaling(raw_darkness)
        return round(los * darkness)

    def _setup(self):
        pass

    def hp_zero(self):
        logger.info(f'{self} died.')
        self._respawn_gold = self.engine.get_stats(self.uid, STAT.GOLD)
        self.engine.set_status(self.uid, STATUS.RESPAWN, self._respawn_timer, 1)
        Assets.play_sfx('ui', 'unit-death', volume='feedback')

    def status_zero(self, status):
        logger.debug(f'{self} lost status: {status.name}.')
        if status is STATUS.RESPAWN:
            self.respawn()

    def respawn(self, reset_gold=True):
        logger.debug(f'{self} respawned.')
        max_hp = self.engine.get_stats(self.uid, STAT.HP, VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.HP, max_hp)
        max_mana = self.engine.get_stats(self.uid, STAT.MANA, VALUE.MAX)
        self.engine.set_stats(self.uid, STAT.MANA, max_mana)
        self.engine.set_position(self.uid, self._respawn_location)
        self.engine.set_position(self.uid, self._respawn_location, value_name=VALUE.TARGET)
        self.engine.kill_dmods(self.uid)
        self.engine.kill_statuses(self.uid)
        if reset_gold:
            self.engine.set_stats(self.uid, STAT.GOLD, self._respawn_gold)

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
            f'Draft cost: {self.total_draft_cost}',
            f'Current velocity: {s2ticks(velocity):.2f}/s ({velocity:.2f}/t)',
            f'Action phase: {self.uid % self.api.engine.AGENCY_PHASE_COUNT}',
            f'Agency: {self.api.engine.timers["agency"][self.uid].mean_elapsed_ms:.3f} ms',
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


class Player(Unit):
    say = 'Let\'s defeat the boss!'

    def _setup(self):
        self._respawn_timer = 500
        self._respawn_timer_scaling = 100
        Assets.play_sfx('ability', 'player-respawn', volume='feedback')

    def hp_zero(self):
        super().hp_zero()

    def respawn(self):
        super().respawn(reset_gold=False)
        self._respawn_timer += self._respawn_timer_scaling
        Assets.play_sfx('ability', 'player-respawn', volume='feedback')


class Creep(Unit):
    say = 'I\'m coming for that fort!'
    def _setup(self):
        self.color = (1, 0, 0)
        self.wave_interval = int(float(self.p['wave']) * 100)
        self.wave_offset = int(float(self.p['wave_offset']) * 100)
        self.scaling = float(self.p['scaling']) if 'scaling' in self.p else 1
        # Space out the wave, as collision is finnicky at the time of writing
        self._respawn_location += RNG.random(2) * self.engine.get_stats(self.uid, STAT.HITBOX) * 0.5
        # Prepare the first wave
        self.first_wave = True
        self.engine.set_position(self.uid, (-1_000_000, -1_000_000))
        self.engine.set_stats(self.uid, STAT.HP, 0)
        self.engine.set_status(self.uid, STATUS.RESPAWN, self._respawn_timer + 1, 1)

    @property
    def target(self):
        return self.engine.units[0]._respawn_location

    def respawn(self):
        super().respawn()
        if self.first_wave is False:
            self.scale_power()
        self.first_wave = False
        self.use_ability(ABILITY.WALK, self.target)
        Assets.play_sfx('ability', 'wave-respawn', volume='feedback', replay=False)

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
        self.use_ability(self.ability_slots[0], self.target)
        for aid in self.ability_slots[1:]:
            if aid is None:
                continue
            self.use_ability(aid, None)

    def debug_str(self, *a, **k):
        return f'{super().debug_str(*a, **k)}\nSpawned at: {self._respawn_location}\nNext wave: {self._respawn_timer}'


class Camper(Unit):
    say = '"Personal space... I need my personal space..."'
    def _setup(self):
        self.color = (1, 0, 0)
        if len(self.abilities) == 0:
            self.set_abilities([ABILITY.WALK, ABILITY.ATTACK])
        self.camp = self.engine.get_position(self.uid)
        self.__aggro_range = float(self.p['aggro_range'])
        self.__deaggro_range = float(self.p['deaggro_range'])
        self.__reaggro_range = float(self.p['reaggro_range'])
        self.__camp_spread = float(self.p['camp_spread'])
        self.__deaggro = False
        self.__walk_target = self.camp
        self.__next_walk = self.engine.tick

    def action_phase(self):
        player_pos = self.engine.get_position(0)
        camp_dist = self.engine.get_distances(self.camp, self.uid)
        in_aggro_range = self.engine.unit_distance(self.uid, 0) < self.__aggro_range
        if in_aggro_range and not self.__deaggro and self.engine.units[0].is_alive:
            for aid in self.ability_slots:
                if aid is None:
                    continue
                self.use_ability(aid, player_pos)
            if camp_dist > self.__deaggro_range:
                self.__deaggro = True
        else:
            if self.__deaggro is True and camp_dist < self.__reaggro_range:
                    self.__deaggro = False
            self.use_ability(self.ability_slots[0], self.walk_target)

    @property
    def walk_target(self):
        if self.__next_walk <= self.engine.tick:
            self.__walk_target = self.camp+(RNG.random(2) * self.__camp_spread*2 - self.__camp_spread)
            self.__next_walk = self.engine.tick + SEED.r * 500
        return self.__walk_target

    def debug_str(self, *a, **k):
        return f'{super().debug_str(*a, **k)}\nCamping at: {self.camp}'


class Boss(Camper):
    say = 'Foolishly brave are we?'
    def _setup(self):
        self.win_on_death = True
        super()._setup()


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


class Fort(Fountain):
    say = 'If I fall, it is all for naught'
    def _setup(self):
        self.set_abilities([ABILITY.FORT_AURA])
        self.engine.set_stats(self.uid, STAT.WEIGHT, -1)
        self.lose_on_death = True


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
