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
    'MANA',
    'GOLD',
    'PHYSICAL',
    'FIRE',
    'EARTH',
    'AIR',
    'WATER',
]

STATUSES = [
    # Meta
    'RESPAWN',
    'FOUNTAIN',
    'SHOP',
    'MAP_EDITOR',
    # Mechanics
    'ARMOR',
    'SLOW',
]

ABILITIES = [*RDF(RDF.CONFIG_DIR / 'abilities.rdf').keys()]


def get_api():
    from logic.game import GameAPI
    return GameAPI()
