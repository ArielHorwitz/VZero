import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


VERSION = 0.016
APP_NAME = 'VZero'
TITLE = f'{APP_NAME} v{VERSION:.3f}'


from pathlib import Path

ROOT_DIR = Path.cwd()
FPS = 60
TPS = 100
BASE_RESOLUTION = 1024, 768
APP_COLOR = (0.2, 0, 0.5, 1)


logger.info(f'Loading {TITLE}...')
logger.info(f'FPS: {FPS} TPS: {TPS} BASE_RESOLUTION: {BASE_RESOLUTION} APP_COLOR {APP_COLOR}')


class CorruptedDataError(Exception):
    pass


def resource_name(name):
    return name.lower().replace(' ', '-').replace('_', '-')


from data.settings import PROFILE
DEV_BUILD = PROFILE.get_setting('misc.dev_build*')
logger.info(f'DEV_BUILD: {"enabled" if DEV_BUILD else "disabled"}')
