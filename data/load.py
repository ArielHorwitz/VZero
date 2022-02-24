import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from pathlib import Path
from nutil.file import file_load, file_dump
from nutil.vars import try_float
from data import ROOT_DIR


class SubCategory(dict):
    def __init__(self, raw_data=None):
        if raw_data is None:
            raw_data = {0: []}
        self.positional = raw_data[0]
        del raw_data[0]
        super().__init__(raw_data)

    def __repr__(self):
        return f'<RDF SubCategory; positional {self.positional} {super().__repr__()}>'


class Category(dict):
    def __init__(self, raw_data):
        if raw_data is None:
            raw_data = {0: {0: []}}
        self.default = SubCategory(raw_data[0])
        del raw_data[0]
        super().__init__({k: SubCategory(v) for k, v in raw_data.items()})

    def __repr__(self):
        return f'<RDF Category; default: {repr(self.default)}; {f"; ".join(f"{k}: {repr(v)}" for k, v in self.items())}>'


class RDF(dict):
    CONFIG_DIR = ROOT_DIR / 'config'
    @classmethod
    def from_str(cls, str, *a, **k):
        return cls(str, *a, **k)

    @classmethod
    def from_file(cls, file, *a, **k):
        return cls(file_load(file), *a, **k)

    def __init__(self, raw_str, convert_float=False):
        self.raw_dict = self._read_toplevel(raw_str.split('\n'), convert_float)
        super().__init__({k: Category(v) for k, v in self.raw_dict.items()})

    @classmethod
    def _read_toplevel(cls, lines, convert_float):
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
                if category in data:
                    nonce = 1
                    while f'{category}.{nonce}' in data:
                        nonce += 1
                    category = f'{category}.{nonce}'
                data[category] = cls._read_category(category_lines, convert_float)
        return data

    @classmethod
    def _read_category(cls, lines, convert_float):
        data = {}
        subcategory_lines = []
        while not lines[0].startswith('-'):
            subcategory_lines.append(lines.pop(0))
            if len(lines) == 0:
                break
        data[0] = cls._read_subcategory(subcategory_lines, convert_float)

        if len(lines) == 0:
            return data

        while lines[0].startswith('-'):
            subcategory_name = lines.pop(0).split('- ', 1)[1]
            subcategory_lines = []
            while len(lines) > 0 and not lines[0].startswith('-'):
                subcategory_lines.append(lines.pop(0))
                if len(lines) == 0:
                    break
            if subcategory_name in data:
                nonce = 1
                while f'{subcategory_name}.{nonce}' in data:
                    nonce += 1
                subcategory_name = f'{subcategory_name}.{nonce}'
            data[subcategory_name] = cls._read_subcategory(subcategory_lines, convert_float)
            if len(lines) == 0:
                break
        return data

    @classmethod
    def _read_subcategory(cls, lines, convert_float):
        positional_values = []
        keyed_values = {}
        for line in lines:
            escape_keyvalue = False
            if line.startswith('~'):
                escape_keyvalue = True
                line = line[1:]
                if line == '':
                    line = ' '
            if ': ' in line and not escape_keyvalue:
                k, v = line.split(': ', 1)
                keyed_values[k] = try_float(v) if convert_float else v
            elif line != '':
                positional_values.append(try_float(line) if convert_float else line)
        keyed_values[0] = positional_values
        return keyed_values

    def save(self, file):
        file_dump(file, self.export_str)

    @property
    def export_str(self):
        d = []
        for category, cdata in self.items():
            d.append(f'\n=== {category}')
            d.append(self.export_category_str(cdata))
        d.append('')
        return '\n'.join(d)

    @classmethod
    def export_category_str(cls, data):
        d = [cls.export_subcategory_str(data.default)]
        for subcategory, scdata in data.items():
            d.append(f'--- {subcategory}')
            d.append(cls.export_subcategory_str(scdata))
        return '\n'.join(d)

    @classmethod
    def export_subcategory_str(cls, data):
        d = []
        for p in data.positional:
            if ': ' in p:
                p = f'~{p}'
            d.append(p)
        for k, v in data.items():
            if isinstance(v, float):
                v = int(v) if v == int(v) else v
            d.append(f'{k}: {v}')
        return '\n'.join(d)
