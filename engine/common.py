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
