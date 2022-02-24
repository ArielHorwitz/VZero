import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


VERSION = 0.016
DEV_BUILD = True

APP_NAME = 'VZero'
TITLE = f'{APP_NAME} v{VERSION:.3f}'

FPS = 60
TPS = 100
BASE_RESOLUTION = 1024, 768
APP_COLOR = (0.2, 0, 0.5, 1)


logger.info(f'Loading {TITLE} {"DEV_BUILD" if DEV_BUILD else ""}...')
logger.info(f'FPS: {FPS} TPS: {TPS} BASE_RESOLUTION: {BASE_RESOLUTION} APP_COLOR {APP_COLOR}')


class CorruptedDataError(Exception):
    pass


import pathlib
ROOT_DIR = pathlib.Path.cwd()

def resource_name(name):
    return name.lower().replace(' ', '-').replace('_', '-')
