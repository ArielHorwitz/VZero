from data import FPS, TPS, resource_name, CorruptedDataError
from logic import internal_name
from logic import ABILITY
from logic import STAT
from logic import VALUE
from logic import STATUS
from logic import STATUS_VALUE
from logic import FAIL_RESULT
from logic import VisualEffect
from logic import COLOR
from logic import VFX


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
