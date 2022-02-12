from data import FPS, TPS, resource_name
from engine import ABILITY
from engine import STAT
from engine import VALUE
from engine import STATUS
from engine import STATUS_VALUE
from engine import FAIL_RESULT
from engine import VisualEffect
from engine import COLOR
from engine import VFX
from engine import internal_name


def str2stat(name):
    return getattr(STAT, name.upper())


def str2value(name):
    return getattr(VALUE, name.upper())


def str2statvalue(s):
    stat_name, value_name = s.split('.') if '.' in s else (s, 'current')
    return str2stat(stat_name), str2value(value_name)


def str2status(name):
    return getattr(STATUS, name.upper())


def str2status_value(name):
    return getattr(STATUS_VALUE, name.upper())


def str2ability(s):
    return getattr(ABILITY, internal_name(s))


def str2color(s):
    if hasattr(COLOR, s.upper()):
        return getattr(COLOR, s.upper())
    else:
        rgb = tuple(float(_) for _ in s.split(', '))
        assert len(rgb) >= 3
        return tuple(rgb[:4])


def str2vfx(s):
    return getattr(VFX, internal_name(s))


def s2ticks(s=1):
    return TPS * s


def ticks2s(t=1):
    return t / TPS


STAT_LIST = list(STAT)
STAT2STATUS = {s: str2status(s.name) for s in STAT if hasattr(STATUS, s.name)}
AID_LIST = list(ABILITY)


class CorruptedDataError(Exception):
    pass
