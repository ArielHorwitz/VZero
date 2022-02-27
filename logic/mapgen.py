import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import random
import numpy as np
from pathlib import Path
from collections import namedtuple, defaultdict
from nutil.file import file_dump

from data import resource_name
from data.load import RDF
from data.tileset import TileMap

from logic.common import *
from logic.units import Unit


TILE_SIZE = 100, 100
Biome = namedtuple('Biome', ['pos', 'tile'])
BIOME_TYPES = [
    'brick',
    'grass',
    'cloud',
    'sand',
    'water',
    'snow',
    'chaos',
    'cursed',
    'earth',
    'lava',
]


class MapGenerator:
    def __init__(self, api, encounter_params):
        self.api = api
        self.encounter_params = encounter_params
        self.map_name = self.encounter_params.map
        self.__map_image_source = None
        self.engine = api.engine
        self.size = np.full(2, 10_000)
        self.player_spawn = self.size/2
        self.spawns = []
        self.biomes = []
        self.generate_map()
        self.spawn_map()
        for unit in self.engine.units:
            unit.setup()

    def setup(self, interface):
        self.gui = interface
        self.generate_map_image()

    def add_spawn(self, spawn, location, quadrant=False):
        self.spawns.append((spawn, np.array(location) * self.size))

    def add_biome(self, tile, center, quadrant=False):
        logger.debug(f'Added {tile} biome at {center}')
        self.biomes.append(Biome(np.array(center), tile))

    def generate_map(self):
        map_data = MAP_DATA[self.map_name]['map']
        if 'Metadata' not in map_data:
            raise CorruptedDataError(f'Map metadata missing from {self.map_name}!')
        metadata = map_data['Metadata'].default
        self.size = np.array([float(_) for _ in metadata['size'].split(', ')])
        if 'source' in metadata:
            self.__map_image_source = metadata['source']
        biomes = map_data['Biomes']
        for tile, biome in biomes.items():
            for raw_point in biome.positional:
                p = [float(_) for _ in raw_point.split(', ')]
                self.add_biome(tile.lower(), p)
        self.__biome_pos = np.array([[*b.pos] for b in self.biomes], dtype=np.float64)

    def spawn_map(self):
        def s2v(s):
            return tuple(float(_) for _ in s.split(', '))
        spawn_data = MAP_DATA[self.map_name]['spawns']
        assert 'Spawn' in spawn_data
        raw_player_spawn = spawn_data['Spawn']['loc'].positional[0]
        self.player_spawn = np.array(s2v(raw_player_spawn)) + 0.1
        self.spawn_unit('player', self.player_spawn)
        for spawn_name, sdata in spawn_data.items():
            if 'loc' not in sdata:
                raise CorruptedDataError(f'{spawn_name} missing locations!')
            for raw_pos in sdata['loc'].positional:
                pos = s2v(raw_pos)
                if 'units' not in sdata:
                    raise CorruptedDataError(f'{spawn_name} missing units!')
                for unit, count in sdata['units'].items():
                    for i in range(int(count)):
                        self.spawn_unit(unit, pos)

    def spawn_unit(self, unit_type, location):
        uid = self.engine.next_uid
        unit = Unit.from_data(self.api, uid, unit_type)
        unit.set_spawn_location(location)
        self.engine.add_unit(unit, unit.starting_stats)
        logger.debug(f'Spawned new unit: {unit} @{location}')

    def refresh(self):
        self.__biome_pos = np.array([[*b.pos] for b in self.biomes], dtype=np.float64)
        self.generate_map_image()

    def generate_map_image(self):
        if self.__map_image_source is not None:
            self.image = str(MAP_DIR / f'{self.__map_image_source}.png')
            logger.info(f'using map source: {self.image}')
            self.gui.request('set_map_source', self.image, self.size)
            return
        tile_resolution = np.array(self.size / TILE_SIZE, dtype=np.int16)
        logger.debug(f'Building map image using tile size: {TILE_SIZE} resolution: {tile_resolution}')
        for b in self.biomes:
            logger.debug(f'Biome: {b}')
        tilemap = {}

        biome_cores = np.array([[*b.pos] for b in self.biomes], dtype=np.float64)
        biome_cores = biome_cores.reshape(len(biome_cores), 1, 1, 2)
        x = np.linspace(TILE_SIZE[0]/2, self.size[0]-TILE_SIZE[0]/2, tile_resolution[0])
        y = np.linspace(TILE_SIZE[1]/2, self.size[1]-TILE_SIZE[1]/2, tile_resolution[1])
        tiles_pos = np.stack(np.meshgrid(x, y), axis=2)[np.newaxis, :]
        dist_vectors = tiles_pos - biome_cores
        tiles_biome_dist = np.linalg.norm(dist_vectors, axis=-1)
        nearest_biomes = np.argmin(tiles_biome_dist, axis=0)
        for x in range(tile_resolution[1]):
            for y in range(tile_resolution[0]):
                b = nearest_biomes[x, y]
                tilemap[(y, x)] = self.biomes[b].tile

        if self.api.dev_mode:
            for b in self.biomes:
                xy = tuple(round(_) for _ in tuple(b.pos / TILE_SIZE))
                tilemap[xy] = 'black'

        self.image = TileMap.draw_map(size=tile_resolution, default='brick', tilemap=tilemap)
        logger.info(f'new map source: {self.image}')
        self.gui.request('set_map_source', self.image, self.size)

    def export_biomes(self):
        logger.info(f'Exporting biomes...')
        biomes = defaultdict(lambda: list())
        for b in self.biomes:
            biomes[b.tile].append(b.pos)
        s = [
            '=== Metadata',
            ', '.join(str(_) for _ in self.size),
            '=== Biomes',
        ]
        for tile, points in biomes.items():
            s.append(f'--- {tile}')
            for point in points:
                s.append(f'{point[0]:.1f}, {point[1]:.1f}')
        e = '\n'.join(s)
        file_dump(MAP_DIR / 'exported.rdf', e)

    def find_biome(self, point):
        nearest_biome = self.nearest_biome_index(point)
        biome = self.biomes[nearest_biome]
        bindex = BIOME_TYPES.index(biome.tile)
        logger.debug(f'Found biome: {biome} {bindex}')
        return bindex

    def nearest_biome_index(self, point):
        dist_vectors = self.__biome_pos - point
        biome_dist = np.linalg.norm(dist_vectors, axis=-1)
        nearest_biome = np.argmin(biome_dist)
        return nearest_biome

    def add_droplet(self, biome, point):
        self.add_biome(BIOME_TYPES[round(biome)], point)
        self.refresh()

    def remove_droplet(self, point):
        nearest_biome = self.nearest_biome_index(point)
        self.biomes.pop(nearest_biome)
        self.refresh()

    def toggle_droplet(self, point):
        nearest_biome = self.nearest_biome_index(point)
        b = self.biomes[nearest_biome]
        new_tile = BIOME_TYPES[BIOME_TYPES.index(b.tile)-1]
        self.biomes[nearest_biome] = Biome(b.pos, new_tile)
        self.refresh()


MAP_DIR = RDF.CONFIG_DIR / 'maps'
assert MAP_DIR.is_dir()

MAP_DATA = {}
for map_file in MAP_DIR.iterdir():
    if not map_file.name.endswith('.rdf'):
        continue
    if map_file.name.endswith('-spawns.rdf'):
        continue
    map_name = map_file.name[:-4]  # strip '.rdf' extension
    spawn_file = MAP_DIR / f'{map_name}-spawns.rdf'
    if not spawn_file.is_file():
        logger.info(f'skipping map_file {map_file.name}, no matching spawns file')
        continue
    map_data = RDF.from_file(map_file, convert_float=True)
    spawn_data = RDF.from_file(spawn_file, convert_float=True)
    MAP_DATA[map_name] = {
        'map': map_data,
        'spawns': spawn_data,
    }
    logger.info(f'Loaded map: {map_name}\n{map_data}\n{spawn_data}')

MAP_NAMES = list(MAP_DATA.keys())
