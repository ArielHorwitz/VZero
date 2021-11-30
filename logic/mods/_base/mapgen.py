import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import copy, random
import numpy as np
from collections import namedtuple, defaultdict

from data import resource_name
from data.load import RDF
from data.tileset import TileMap
from logic.mechanics.common import *


Biome = namedtuple('Biome', ['pos', 'weight', 'tile'])
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

def set_spawn_location(stats, spawn):
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.CURRENT] = spawn
    stats[(STAT.POS_X, STAT.POS_Y), VALUE.TARGET_VALUE] = spawn


class MapGenerator:
    TERRITORY_SIZE = 1000

    def __init__(self, api, unit_types):
        self.api = api
        self.unit_types = unit_types
        self.size = np.full(2, 10_000)
        self.player_spawn = self.size/2
        self.spawns = []
        self.biomes = []
        self.request_redraw = -1
        self.generate_map()
        self.generate_map_image()

    def add_spawn(self, spawn, location, quadrant=False):
        self.spawns.append((spawn, np.array(location) * self.size))

    def add_biome(self, tile, center, weight=1, quadrant=False):
        logger.debug(f'Added {tile} biome at: {center} (weight: {weight})')
        self.biomes.append(Biome(np.array(center) * self.size, weight, tile))

    def generate_map(self):
        map_data = RDF(RDF.CONFIG_DIR / 'map.rdf')
        biomes = map_data['Biomes']
        for tile, biome in biomes.items():
            for raw_point in biome.positional:
                p = [float(_) for _ in raw_point.split(', ')]
                weight = 1
                if len(p) == 3:
                    weight = p[2]
                    p = p[:2]
                p = np.array(p)/100
                self.add_biome(tile.lower(), p, weight=weight)

        self.player_spawn = None
        spawns = map_data['Spawns']
        for spawn, points in spawns.items():
            for raw_point in points.positional:
                p = [float(_) for _ in raw_point.split(', ')]
                p = np.array(p, dtype=np.float64)/100
                if spawn == 'Spawn':
                    self.player_spawn = self.size * p - (0, 0.1)
                self.add_spawn(spawn, p)
        if self.player_spawn is None:
            raise ValueError(f'Missing player spawn in map config!')

    def spawn_map(self):
        spawn_type_options = RDF(RDF.CONFIG_DIR / 'spawn_types.rdf')
        for spawn, location in self.spawns:
            spawn_options = tuple(spawn_type_options[spawn].keys())
            spawn_choice = random.choice(spawn_options)
            spawn_spec = spawn_type_options[spawn][spawn_choice]
            units = spawn_spec.items()
            for i, (utype, amount) in enumerate(units):
                for j in range(int(amount)):
                    self.spawn_unit(utype, location)

    def spawn_unit(self, unit_type, location):
        internal_name = resource_name(unit_type)
        unit_data = self.unit_types[internal_name]
        unit_cls = unit_data['cls']
        name = copy.deepcopy(unit_data['name'])
        stats = unit_data['stats']
        set_spawn_location(stats, location)
        setup_params = copy.deepcopy(unit_data['setup_params'])
        unit = self.api.add_unit(unit_cls, name, stats, setup_params)
        logger.debug(f'Created new unit {internal_name} with uid {unit.uid} and setup_params: {setup_params}')
        return unit

    def generate_map_image(self):
        tile_resolution = np.array([100, 100])
        tile_size = self.size / tile_resolution
        logger.debug(f'Building map image using tile size: {tile_size} resolution: {tile_resolution}')
        for b in self.biomes:
            logger.debug(f'Biome: {b}')
        tilemap = {}

        biome_cores = np.array([[*b.pos] for b in self.biomes], dtype=np.float64)
        biome_cores = biome_cores.reshape(len(biome_cores), 1, 1, 2)
        x = np.linspace(tile_size[0]/2, self.size[0]-tile_size[0]/2, tile_resolution[0])
        y = np.linspace(tile_size[1]/2, self.size[1]-tile_size[1]/2, tile_resolution[1])
        tiles_pos = np.stack(np.meshgrid(x, y), axis=2)[np.newaxis, :]
        dist_vectors = tiles_pos - biome_cores
        tiles_biome_dist = np.linalg.norm(dist_vectors, axis=-1)
        biome_weights = np.array([b.weight for b in self.biomes], dtype=np.float64)
        biome_weights = biome_weights.reshape(len(biome_cores), 1, 1)
        tiles_biome_dist /= biome_weights
        nearest_biomes = np.argmin(tiles_biome_dist, axis=0)
        for x in range(tile_resolution[0]):
            for y in range(tile_resolution[1]):
                # Not quite sure where things are flipped, but we draw correctly when x and y are flipped
                # Might be an issue here or in data.tileset.Tileset
                tilemap[(y, x)] = self.biomes[nearest_biomes[x, y]].tile

        for b in self.biomes:
            x, y = (int(_) for _ in b.pos / tile_resolution)
            # tilemap[(x, y)] = 'black'

        self.image = TileMap.draw_map(
            size=tile_resolution,
            default='brick',
            tilemap=tilemap,
        )
        self.request_redraw = self.api.tick
        self.export_biomes()

    def export_biomes(self):
        biomes = defaultdict(lambda: list())
        for b in self.biomes:
            biomes[b.tile].append(b.pos)
        s = []
        for tile, points in biomes.items():
            s.append(f'--- {tile}')
            for point in points:
                p = np.array(point) / self.size * 100
                s.append(f'{p[0]:.1f}, {p[1]:.1f}')
        e = '\n'.join(s)
        logger.debug(f'Exported biomes:\n{e}')

    def find_biome(self, point):
        nearest_biome = self.nearest_biome_index(point)
        biome = self.biomes[nearest_biome]
        bindex = BIOME_TYPES.index(biome.tile)
        logger.debug(f'Found biome: {biome} {bindex}')
        return bindex

    def nearest_biome_index(self, point):
        biome_cores = np.array([[*b.pos] for b in self.biomes], dtype=np.float64)
        dist_vectors = biome_cores - point
        biome_dist = np.linalg.norm(dist_vectors, axis=-1)
        biome_dist /= np.array([b.weight for b in self.biomes], dtype=np.float64)
        nearest_biome = np.argmin(biome_dist)
        return nearest_biome

    def add_droplet(self, biome, point):
        self.add_biome(BIOME_TYPES[round(biome)], point / self.size)
        self.generate_map_image()

    def remove_droplet(self, point):
        nearest_biome = self.nearest_biome_index(point)
        self.biomes.pop(nearest_biome)
        self.generate_map_image()

    def toggle_droplet(self, point):
        nearest_biome = self.nearest_biome_index(point)
        b = self.biomes[nearest_biome]
        new_tile = BIOME_TYPES[BIOME_TYPES.index(b.tile)-1]
        self.biomes[nearest_biome] = Biome(b.pos, b.weight, new_tile)
        self.generate_map_image()
