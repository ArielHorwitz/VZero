
from PIL import Image
import os, tempfile
from pathlib import Path
from nutil.random import Seed


TILESET_DIR = Path.cwd()/'assets'/'graphics'/'tiles/'
TILESETS = {
    'tiles1.png': (16, 16),
}


class Tileset:
    def __init__(self, tileset_name=None):
        if tileset_name is None:
            tileset_name = list(TILESETS.keys())[0]
        tileset_file = str(TILESET_DIR/tileset_name)
        print('ts file:', tileset_file)
        im = Image.open(tileset_file)
        print(f'Loaded tileset file with format {im.format}, size {im.size}, mode {im.mode}')
        self.all_tiles = []
        self.tiles = {}
        self.w, self.h = w, h = TILESETS[tileset_name][:2]
        assert im.size[0] % w == 0 and im.size[1] % h == 0
        for row in range(int(im.size[0]/h)):
            for column in range(int(im.size[1]/w)):
                x, y = column*w, row*h
                box = (x, y, x+w, y+h)
                region = im.crop(box)
                self.all_tiles.append(region)
        self.categorize_tiles()

    def categorize_tiles(self):
        self.tiles['grass'] = self.all_tiles[:7]

    def make_map(self, tiles_x, tiles_y):
        s = Seed('dev')
        size = tiles_x * self.w, tiles_y * self.h
        print('tilemap size', size)
        new_map = Image.new(mode='RGB', size=size)
        for x in range(tiles_x):
            for y in range(tiles_y):
                tile = s.choice(self.tiles['grass'])
                location = x * self.w, y * self.h
                new_map.paste(tile, location)
        save_dir = tempfile.TemporaryDirectory().name
        map_file = save_dir + 'map.jpg'
        print('map file', map_file)
        new_map.save(map_file)
        return map_file
