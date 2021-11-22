import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from pathlib import Path
from nutil.file import file_load
from nutil.vars import try_float
from data import ROOT_DIR


class SubCategory(dict):
    def __init__(self, raw_data):
        self.positional = raw_data[0]
        del raw_data[0]
        super().__init__(raw_data)


class Category(dict):
    def __init__(self, raw_data):
        self.default = raw_data[0]
        del raw_data[0]
        super().__init__({k: SubCategory(v) for k, v in raw_data.items()})


class RDF(dict):
    CONFIG_DIR = ROOT_DIR / 'config'
    def __init__(self, file):
        self.raw_dict = self.load(file)
        super().__init__({k: Category(v) for k, v in self.raw_dict.items()})

    @classmethod
    def load(cls, file):
        return cls._read_toplevel(cls._get_lines(file))

    @classmethod
    def _get_lines(cls, file):
        raw = file_load(file)
        lines = raw.split('\n')
        return lines

    @classmethod
    def _read_toplevel(cls, lines):
        data = {}
        while len(lines) > 0:
            line = lines.pop(0)
            if line.startswith('='):
                category = line.split('= ', 1)[1]
                category_lines = []
                while not lines[0].startswith('='):
                    category_lines.append(lines.pop(0))
                    if len(lines) == 0:
                        break
                data[category] = cls._read_category(category_lines)
        return data

    @classmethod
    def _read_category(cls, lines):
        data = {}
        subcategory_lines = []
        while not lines[0].startswith('-'):
            subcategory_lines.append(lines.pop(0))
            if len(lines) == 0:
                break
        data[0] = cls._read_subcategory(subcategory_lines)

        if len(lines) == 0:
            return data

        while lines[0].startswith('-'):
            subcategory_name = lines.pop(0).split('- ', 1)[1]
            subcategory_lines = []
            while not lines[0].startswith('-'):
                subcategory_lines.append(lines.pop(0))
                if len(lines) == 0:
                    break
            data[subcategory_name] = cls._read_subcategory(subcategory_lines)
            if len(lines) == 0:
                break
        return data

    @classmethod
    def _read_subcategory(cls, lines):
        positional_values = []
        keyed_values = {}
        for line in lines:
            if ': ' in line:
                k, v = line.split(': ', 1)
                keyed_values[k] = try_float(v)
            elif line != '':
                positional_values.append(try_float(line))
        keyed_values[0] = positional_values
        return keyed_values


#
# ABILITIES_FILE = CONFIG_DIR / 'abilities.bal'
# UNITS_FILE = CONFIG_DIR / 'units.bal'
# MAP_FILE = CONFIG_DIR / 'map.bal'
#
# class LoadMechanics:
#     RAW_ABILITY_DATA = LoadBalFile.load_toplevel(ABILITIES_FILE)
#     RAW_UNIT_DATA = LoadBalFile.load_toplevel(UNITS_FILE)
#
