import numpy as np
from data.tileset import TileMap



class ModEncounterAPI:
    def __init__(self, api):
        self.api = api
        self.map_size = np.full(2, 5_000)
        self.map_image_source = TileMap(['tiles1']).make_map(100, 100)

    def spawn_map(self):
        logger.warning(f'Base class of ModEncounterAPI does not spawn anything.')
