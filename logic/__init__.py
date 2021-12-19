# Logic definitions
"""
This module is imported by the engine to define
common enumerators. We provide these before
importing the rest of the package since we
rely on those enumerators in runtime.
"""


from data.load import RDF


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
    # Mechanics
    'SLOW',
    'BOUNDED',
    'CUTS',
    'VANITY',
    'ARMOR',
    'REFLECT',
    'SPIKES',
    'LIFESTEAL',
]

STATUSES = [
    # Meta
    'RESPAWN',
    'FOUNTAIN',
    'SHOP',
    'MAP_EDITOR',
    # Mechanics
    'ARMOR',
    'LIFESTEAL',
    'SPIKES',
    'VANITY',
    'SLOW',
    'REFLECT',
    'CUTS',
    'BOUNDED',
]

ABILITIES = [*RDF(RDF.CONFIG_DIR / 'abilities.rdf').keys()]


def get_api():
    from logic.game import GameAPI
    return GameAPI()
