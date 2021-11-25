import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
from data.tileset import TileMap



class ModEncounterAPI:
    menu_title = 'Mod menu not implemented'
    menu_texts = ['Click me (left or right) and check log']
    menu_colors = [(0, 0, 0)]

    def __init__(self, api):
        self.api = api
        self.map_size = np.full(2, 5_000)
        self.map_image_source = TileMap(['tiles1']).make_map(100, 100)

    def spawn_map(self):
        logger.warning(f'Base class of ModEncounterAPI does not spawn anything.')

    def menu_click(self, index, right_click):
        logger.warning(f'{self.__class__}.menu_click() not implemented.')
        logger.debug(f'Mod menu clicked: {index} (right click: {right_click})')
        return 'ui', 'target'
