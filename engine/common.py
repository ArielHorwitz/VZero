from engine import ABILITY
from engine import STAT
from engine import VALUE
from engine import STATUS
from engine import STATUS_VALUE
from engine import FAIL_RESULT
from engine import VisualEffect
from engine import COLOR
from engine import internal_name


def str2stat(name):
    return getattr(STAT, name.upper())


def str2value(name):
    return getattr(VALUE, name.upper())


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
        return tuple(rgb[:3])


AID_LIST = list(ABILITY)
