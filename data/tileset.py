import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
import collections, tempfile
from PIL import Image
from pathlib import Path
from nutil.random import Seed, SEED


TILESET_DIR = Path.cwd() / 'assets' / 'graphics' / 'tiles'
TILESET_METADATA = {
    'tiles': {
        'tile_size': 32,
        'categories': [name for name in [
            'lava',
            'earth',
            'grass',
            'cursed',
            'sand',
            'water',
            'snow',
            'chaos',
            'brick',
            'cloud',
            'black',
        ] for i in range(6)],
    },
}



class __TileMap:
    def __init__(self, tileset):
        self.last_file = 0
        self.tile_size = None
        self.tiles = collections.defaultdict(lambda: list())
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
        logger.info(f'Loading tileset file with format {im.format}, size {im.size}, mode {im.mode}')

        size = TILESET_METADATA[tileset]['tile_size']
        assert im.size[0] % size == 0 and im.size[1] % size == 0
        categories = iter(TILESET_METADATA[tileset]['categories'])
        for row in range(int(im.size[1]/size)+1):
            for column in range(int(im.size[0]/size)):
                x, y = column*size, row*size
                box = (x, y, x+size, y+size)
                tile = im.crop(box)
                category = next(categories)
                self.tiles[category].append(tile)

    def draw_map(self, size, default, tilemap):
        s = Seed('dev')
        tiles_x, tiles_y = size
        total_size = np.array(size) * self.tile_size
        logger.info(f'Tilemap pixel size: {total_size}')
        new_map = Image.new(mode='RGB', size=tuple(total_size))

        for x in range(tiles_x):
            for y in range(tiles_y):
                location = x * self.tile_size, (tiles_y-y-1) * self.tile_size
                category = default
                if (x, y) in tilemap:
                    category = tilemap[(x, y)]
                tile = s.choice(self.tiles[category])
                new_map.paste(tile, location)

        self.last_file += 1
        map_file = str(Path(tempfile.gettempdir()) / f'vzero-map{self.last_file}.jpg')
        logger.debug(f'Draw map save path: {map_file}')
        new_map.save(map_file)
        return map_file


TileMap = __TileMap('tiles')
