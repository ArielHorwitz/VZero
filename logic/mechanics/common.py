from logic.mechanics import ABILITY
from logic.mechanics import STAT
from logic.mechanics import VALUE
from logic.mechanics import STATUS
from logic.mechanics import STATUS_VALUE
from logic.mechanics import FAIL_RESULT
from logic.mechanics import VisualEffect
from logic.mechanics import COLOR


def str2stat(name):
    return getattr(STAT, name.upper())


def str2value(name):
    return getattr(VALUE, name.upper())


def str2status(name):
    return getattr(STATUS, name.upper())


def str2status_value(name):
    return getattr(STATUS_VALUE, name.upper())
