import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
from data.tileset import TileMap



class ModEncounterAPI:
    request_redraw = 0

    def __init__(self, api):
        self.api = api
        self.map_size = np.full(2, 5_000)
        self.map_image_source = TileMap(['tiles1']).make_map(100, 100)

    def spawn_map(self):
        logger.warning(f'Base class of ModEncounterAPI does not spawn anything.')

    # Reactions
    def hp_zero(self, uid):
        logger.warning(f'{self.__class__}.hp_zero() not implemented.')

    def status_zero(self, uid, status):
        logger.warning(f'{self.__class__}.status_zero() not implemented.')

    # GUI API
    menu_title = 'Mod menu not implemented'
    menu_texts = ['Mod menu has no items']
    menu_colors = [(0, 0, 0)]

    def menu_click(self, index, right_click):
        logger.warning(f'{self.__class__}.menu_click() not implemented.')
        return 'ui', 'target'

    def agent_panel_bars(self, uid):
        return [
            (0.5, (1, 0, 1), f'{self.__class__}.agent_panel_bar() not implemented.'),
            (0, (1, 1, 1), None),
        ]

    def agent_panel_boxes_labels(self, uid):
        return [
            f'{self.__class__}.agent_panel_boxes_labels() not implemented.',
            '',
            '',
            '',
            '',
            '',
        ]

    def agent_panel_boxes_sprites(self, uid):
        logger.warning(f'{self.__class__}.agent_panel_boxes_sprites() not implemented.')
        return [
            ('error', 'error'),
            ('error', 'error'),
            ('error', 'error'),
            ('error', 'error'),
            ('error', 'error'),
            ('error', 'error'),
        ]

    def agent_panel_label(self, uid):
        return f'{self.__class__}.agent_panel_label() not implemented.'
