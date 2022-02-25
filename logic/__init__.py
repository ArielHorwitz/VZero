import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import enum
from nutil.vars import AutoIntEnum
from data.load import RDF
from data.assets import Assets


def internal_name(name):
    return name.upper().replace(' ', '_')


MECHANICS_NAMES = [
    'STOCKS',
    'SHOP',
    'LOS',
    'DARKNESS',
    'MOVESPEED',
    'BOUNDED',
    'SLOW',
    'CUTS',
    'ARMOR',
    'SPIKES',
    'LIFESTEAL',
    'VANITY',
    'REFLECT',
    'SENSITIVITY',
]
STAT = AutoIntEnum('STAT', [
    'POS_X',
    'POS_Y',
    'WEIGHT',
    'HITBOX',
    'HP',
    'ALLEGIANCE',
    'MANA',
    'GOLD',
    'PHYSICAL',
    'FIRE',
    'EARTH',
    'AIR',
    'WATER',
    *MECHANICS_NAMES,
])
assert STAT.POS_X + 1 == STAT.POS_Y
VALUE = AutoIntEnum('VALUE', ['CURRENT', 'MIN', 'MAX', 'DELTA', 'TARGET'])
STATUS = AutoIntEnum('STATUS', [
    'RESPAWN',
    'FOUNTAIN',
    'MAP_EDITOR',
    *MECHANICS_NAMES,
])
STATUS_VALUE = AutoIntEnum('STATUS_VALUE', ['DURATION', 'STACKS'])
ABILITY = AutoIntEnum('ABILITY', [internal_name(_) for _ in RDF.from_file(RDF.CONFIG_DIR / 'abilities.rdf').keys()])
FAIL_RESULT = AutoIntEnum('FAIL_RESULT', [
    'CRITICAL_ERROR',
    'INACTIVE',
    'MISSING_ACTIVE',
    'MISSING_TARGET',
    'MISSING_COST',
    'OUT_OF_BOUNDS',
    'OUT_OF_RANGE',
    'OUT_OF_ORDER',
    'ON_COOLDOWN',
])
VFX = AutoIntEnum('VFX', [
    'BACKGROUND',
    'LINE',
    'CIRCLE',
    'QUAD',
    'SPRITE',
    'SFX',
])


class COLOR:
    BLACK = (0, 0, 0)
    WHITE = (1, 1, 1)
    GREY = (0.5, 0.5, 0.5)
    RED = (1, 0, 0)
    GREEN = (0, 1, 0)
    BLUE = (0, 0, 1)
    YELLOW = (1, 1, 0)
    PURPLE = (1, 0, 1)
    PINK = (0.5, 0, 0)
    CYAN = (0, 1, 1)
    BROWN = (0.5, 0.5, 0)
    LIME = (0.65, 1, 0)


class VisualEffect:
    VFX = VFX
    def __init__(self, eid, ticks, params=None):
        self.eid = eid
        self.total_ticks = ticks
        self.elapsed_ticks = 0
        self.params = {} if params is None else params

        if eid is self.VFX.SFX:
            category = 'abilities'
            if 'category' in params:
                category = params['category']
            volume = 'sfx'
            if 'volume' in params:
                volume = params['volume']
            Assets.play_sfx(f'{category}.{params["sfx"]}', volume=volume)
            self.total_ticks = 0

    def tick(self, ticks):
        self.elapsed_ticks += ticks

    @property
    def active(self):
        return self.elapsed_ticks <= self.total_ticks

    def __repr__(self):
        return f'<VisualEffect eid={self.eid.name} elapsed={self.elapsed_ticks} total={self.total_ticks}>'


for enumerator in (STAT, VALUE, STATUS, STATUS_VALUE, ABILITY):
    __DEBUG = f'Using {enumerator.__name__} indices:'
    for stat in enumerator:
        __DEBUG += f'{stat.value} {stat.name}; '
    logger.info(__DEBUG)


def get_api(*a, **k):
    from logic.game import GameAPI
    return GameAPI(*a, **k)
