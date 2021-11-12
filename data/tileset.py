
import numpy as np
import collections, tempfile
from PIL import Image
from pathlib import Path
from nutil.random import Seed

import logging
logger = logging.getLogger(__name__)


TILESET_DIR = Path.cwd()/'assets'/'graphics'/'tiles'
TILESET_METADATA = {
    'tiles1': {
        'tile_size': 16,
        'categories': [
            *(['grass']*7), 'decoration', 'decoration', *(['grass']*3),
            'stone', 'decoration', *(['stone']*4), 'decoration', 'stone',
            ],
    },
    'lava': {
        'tile_size': 32,
        'categories': [
            *(['lava']*9),
            *(['scorched']*9),
            ],
    },
}


class TileMap:
    def __init__(self, tilesets):
        self.tile_size = None
        self.tiles = collections.defaultdict(lambda: list())
        for tileset in tilesets:
            ts_size = TILESET_METADATA[tileset]['tile_size']
            if self.tile_size is None:
                self.tile_size = ts_size
            if self.tile_size != ts_size:
                raise RuntimeError(f'Cannot import multiple tilesets with different tile sizes ({self.tile_size} != {ts_size})')
            self.load_tiles(tileset)

    def load_tiles(self, tileset):
        tileset_name = f'{tileset}.png'
        tileset_file = str(TILESET_DIR/tileset_name)
        im = Image.open(tileset_file)
        logger.info(f'Loaded tileset file with format {im.format}, size {im.size}, mode {im.mode}')

        size = TILESET_METADATA[tileset]['tile_size']
        assert im.size[0] % size == 0 and im.size[1] % size == 0
        categories = iter(TILESET_METADATA[tileset]['categories'])
        for row in range(int(im.size[0]/size)):
            for column in range(int(im.size[1]/size)):
                x, y = column*size, row*size
                box = (x, y, x+size, y+size)
                tile = im.crop(box)
                try:
                    category = next(categories)
                except StopIteration:
                    return
                self.tiles[next(categories)].append(tile)

    def make_map(self, tiles_x, tiles_y):
        s = Seed('dev')
        total_size = np.array((tiles_x, tiles_y)) * self.tile_size
        logger.debug(f'Tilemap pixel size: {total_size}')
        new_map = Image.new(mode='RGB', size=tuple(total_size))
        for x in range(tiles_x):
            for y in range(tiles_y):
                tile = s.choice(self.tiles['grass'])
                location = x * self.tile_size, y * self.tile_size
                new_map.paste(tile, location)
        save_dir = tempfile.TemporaryDirectory().name
        map_file = save_dir + 'map.jpg'
        new_map.save(map_file)
        return map_file
