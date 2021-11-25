
import math
import numpy as np
from nutil.random import SEED
from nutil.display import njoin
from nutil.vars import normalize, NP
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics


RNG = np.random.default_rng()


class EncounterAPI:
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
    def dev_mode(self):
        return self.e.dev_mode

    @classmethod
    def get_ability(cls, index):
        return Mechanics.abilities[index]

    @property
    def abilities(self):
        return Mechanics.abilities

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

    @property
    def elapsed_time_ms(self):
        return self.e.ticktime * self.e.tick

    # STATS
    @property
    def get_stats(self):
        return self.e.stats.get_stats

    @property
    def set_stats(self):
        return self.e.stats.set_stats

    @property
    def get_status(self):
        return self.e.stats.get_status

    @property
    def set_status(self):
        return self.e.stats.set_status

    @property
    def get_cooldown(self):
        return self.e.stats.get_cooldown

    @property
    def set_cooldown(self):
        return self.e.stats.set_cooldown

    @property
    def get_position(self):
        return self.e.stats.get_position

    @property
    def set_position(self):
        return self.e.stats.set_position

    @property
    def get_velocity(self):
        return self.e.stats.get_velocity

    @property
    def get_distances(self):
        return self.e.stats.get_distances

    @property
    def add_dmod(self):
        return self.e.stats.add_dmod

    @property
    def add_unit(self):
        return self.e.add_unit

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

    def ticks2s(self, ticks=1):
        return ticks / self.e.target_tps

    def s2ticks(self, seconds=1):
        return seconds * self.e.target_tps

    @property
    def timers(self):
        return self.e.timers

    # DEBUG / MISC
    def __init__(self, encounter):
        self.e = encounter

    @property
    def debug(self):
        return self.e.debug_action

    def pretty_stats(self, uid, stats=None):
        unit = self.units[uid]
        if stats is None:
            stats = STAT
        stat_table = self.e.stats.table
        velocity = self.get_velocity(uid)
        s = [
            f'Allegience: {unit.allegiance}',
            f'Speed: {self.s2ticks(velocity):.2f}/s ({velocity:.2f}/t)',
        ]
        for stat in stats:
            current = stat_table[uid, stat, VALUE.CURRENT]
            delta = self.s2ticks()*stat_table[uid, stat, VALUE.DELTA]
            d_str = f' + {delta:.2f}' if delta != 0 else ''
            max_value = stat_table[uid, stat, VALUE.MAX_VALUE]
            mv_str = f' / {max_value:.2f}' if max_value < 100_000 else ''
            s.append(f'{stat.name.lower().capitalize()}: {current:3.2f}{d_str}{mv_str}')
        return njoin(s)

    def pretty_statuses(self, uid):
        s = []
        for status in STATUS:
            v = self.e.stats.status_table[uid, status]
            duration = self.ticks2s(v[STATUS_VALUE.DURATION])
            if duration > 0:
                name_ = status.name.lower().capitalize()
                stacks = v[STATUS_VALUE.STACKS]
                s.append(f'{name_}: {duration:.2f} × {stacks:.2f}')
        return njoin(s)

    def pretty_cooldowns(self, uid):
        s = []
        for ability in ABILITY:
            v = self.get_cooldown(uid, ability)
            if v > 0:
                name_ = ability.name.lower().capitalize()
                s.append(f'{name_}: {self.ticks2s(v):.2f} ({round(v)})')
        return njoin(s)
