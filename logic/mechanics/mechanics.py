
import numpy as np
from logic.mechanics.common import *
from nutil.vars import normalize


class Mechanics:
    @staticmethod
    def attack_speed_to_cooldown(attack_speed):
        return (100 / attack_speed) * 120

    @staticmethod
    def apply_move(api, uid, target=None, move_speed=None):
        if move_speed is None:
            move_speed = api.get_stats(uid, STAT.MOVE_SPEED)
            if api.get_status(uid, STATUS.SLOW) > 0:
                move_speed *= 1-api.get_status(uid, STATUS.SLOW)
        if target is None:
            target = np.array([
                api.get_stats(uid, STAT.POS_X, value_name=VALUE.TARGET_VALUE),
                api.get_stats(uid, STAT.POS_Y, value_name=VALUE.TARGET_VALUE),
                ])
        current_pos = api.get_position(uid)
        target_vector = target - current_pos
        delta = normalize(target_vector, move_speed)
        for i, n in ((0, STAT.POS_X), (1, STAT.POS_Y)):
            api.set_stats(
                uid, n, (delta[i], target[i]),
                value_name=(VALUE.DELTA, VALUE.TARGET_VALUE)
            )

    @staticmethod
    def apply_slow(api, uid, duration, percent):
        api.set_status(uid, STATUS.SLOW, duration, percent)
        Mechanics.apply_move(api, uid)

    @staticmethod
    def do_physical_damage(api, source_uid, target_uid, damage):
        source = api.units[source_uid]
        target = api.units[target_uid]
        api.set_stats(target_uid, STAT.HP, -damage, additive=True)
        lifesteal = api.get_stats(source_uid, STAT.LIFESTEAL)
        lifesteal += api.get_status(source_uid, STATUS.LIFESTEAL)
        api.set_stats(source_uid, STAT.HP, damage*lifesteal, additive=True)
        if target_uid == 0:
            api.add_visual_effect(VisualEffect.BACKGROUND, 40)
            api.add_visual_effect(VisualEffect.SFX, 1, params={'sfx': 'ouch'})
        if target_uid == 0 or source_uid == 0:
            print(f'{api.units[source_uid].name} applied {damage:.2f} damage to {target.name}')
