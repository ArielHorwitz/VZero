# Logic definitions
"""
This module is imported by the engine to define
common enumerators. We provide these before
importing the rest of the package since we
rely on those enumerators in runtime.
"""


from data.load import RDF



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

# Builtin stats: POS_X, POS_Y, WEIGHT, HITBOX, HP
STATS = [
    'ALLEGIANCE',
    'MANA',
    'GOLD',
    'PHYSICAL',
    'FIRE',
    'EARTH',
    'AIR',
    'WATER',
    *MECHANICS_NAMES,
]

STATUSES = [
    'RESPAWN',
    'FOUNTAIN',
    'MAP_EDITOR',
    *MECHANICS_NAMES,
]

ABILITIES = [*RDF(RDF.CONFIG_DIR / 'abilities.rdf').keys()]


def get_api(interface):
    from logic.game import GameAPI
    return GameAPI(interface)
