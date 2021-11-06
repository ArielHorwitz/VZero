
import math
import numpy as np
from nutil.random import SEED
from nutil.display import njoin
from nutil.vars import normalize, NP
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics as Mech


RNG = np.random.default_rng()


class EncounterAPI:
    # UTILITY
    def find_enemy_target(self, uid, target,
            range=None, include_hitbox=True,
            draw_miss_vfx=True,
        ):
        pos = self.get_position(uid)
        if range is None:
            range = self.get_stats(uid, STAT.RANGE)
        enemies = self.mask_enemies(uid)
        target_uid, dist = self.nearest_uid(target, enemies)
        if target_uid is None:
            return None
        attack_pos = self.get_position(target_uid)
        attack_target = self.units[target_uid]
        if include_hitbox:
            range += attack_target.hitbox
        if math.dist(pos, attack_pos) > range:
            if uid == 0 and draw_miss_vfx:
                self.add_visual_effect(VisualEffect.LINE, 10, {
                    'p1': pos,
                    'p2': pos + normalize(attack_pos - pos, range),
                    'color_code': self.units[uid].color_code,
                })
            return None
        return target_uid

    def mask_alive(self):
        return self.get_stats(slice(None), STAT.HP) > 0

    def mask_dead(self):
        return np.invert(self.mask_alive())

    def mask_allies(self, uid):
        a = self.units[uid].allegience
        return np.array([_u.allegience == a for _u in self.units])

    def mask_enemies(self, uid):
        return np.invert(self.mask_allies(uid))

    def nearest_uid(self, point, mask=None, alive=True):
        if mask is None:
            mask = np.ones(len(self.units), dtype=np.int)
        if alive:
            alive = self.get_stats(slice(None), STAT.HP) > 0
            mask = np.logical_and(mask, alive)
        if mask.sum() == 0:
            return None, None
        distances = self.e.stats.get_distances(point)
        uid = NP.argmin(distances, mask)
        return uid, distances[uid]

    def get_offset(self):
        return RNG.random(2) * 30

    def random_location(self):
        return np.array(tuple(SEED.r*_ for _ in self.map_size))

    @property
    def attack_speed_to_cooldown(self):
        return Mech.attack_speed_to_cooldown

    def get_live_monster_count(self):
        return (self.get_stats(slice(None), STAT.HP)>0).sum()

    @property
    def add_visual_effect(self):
        return self.e.add_visual_effect

    # PROPERTIES
    @property
    def map_size(self):
        return self.e.map_size

    @property
    def map_center(self):
        return self.map_size / 2

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
    def get_distances(self):
        return self.e.stats.get_distances

    def debug_stats_table(self):
        return str(self.e.stats.table)

    # GUI UTILITIES
    def do_ticks(self, t=1):
        return self.e._do_ticks(t)

    def set_auto_tick(self, *a, **k):
        return self.e.set_auto_tick(*a, **k)

    def update(self):
        self.e.update()

    def get_visual_effects(self):
        return self.e.get_visual_effects()

    def use_ability(self, *args, **kwargs):
        return self.e.use_ability(*args, **kwargs)

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
        s = [f'#{uid:0>3} .. Allegience: {unit.allegience}']
        for stat in stats:
            current = stat_table[uid, stat, VALUE.CURRENT]
            delta = stat_table[uid, stat, VALUE.DELTA]
            d_str = f' + {delta:.2f}' if delta != 0 else ''
            max_value = stat_table[uid, stat, VALUE.MAX_VALUE]
            mv_str = f' / {max_value:.2f}' if max_value < 100_000 else ''
            s.append(f'{stat.name.lower().capitalize()}: {current:3.2f}{d_str}{mv_str}')
        s.append(f'Statuses:')
        for status in STATUS:
            v = self.e.stats.status_table[uid, status]
            duration = v[STATUS_VALUE.DURATION]
            if duration > 0:
                name_ = status.name.lower().capitalize()
                amplitude = v[STATUS_VALUE.AMPLITUDE]
                s.append(f'{name_}: {duration} *{amplitude}')
        s.append(f'Cooldowns:')
        for ability in ABILITIES:
            v = self.e.stats.cooldowns[uid, ability]
            if v > 0:
                name_ = ability.name.lower().capitalize()
                s.append(f'{name_}: {v:.2f}')
        s.append(f'{unit.debug_str[:30]}')
        return njoin(s)
