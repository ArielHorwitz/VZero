VERSION = 0.010

NAME = f'VZero'

TITLE = f'{NAME} v{VERSION:.3f}'

FPS = 60



import pathlib
ROOT_DIR = pathlib.Path.cwd()

def resource_name(name):
    return name.lower().replace(' ', '-').replace('_', '-')
