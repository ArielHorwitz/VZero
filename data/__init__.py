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
INFO_STR = """
=== VZero
Welcome to VZero. I appreciate your help in testing this early version of the game [b]:)[/b]
~
[u]The game is in early alpha and not intended for public distribution.[/u]
~
This software enables and encourages user modifications for personal use. The developers take no responsibility for user directed content. The software and associated content is provided "as is", without warranty of any kind, express or implied.

-- Software
Written by Ariel Horwitz in Python 3 with Kivy (https://github.com/kivy/kivy).
--- Art
[b]Yisrael Hessler[/b] - https://github.com/imcrazeegamer
[b]Orr Didi[/b] - https://scardust.co
And many more public domain contributions
"""


logger.info(f'Loading {TITLE}...')
logger.info(INFO_STR)
logger.info(f'FPS: {FPS} TPS: {TPS} BASE_RESOLUTION: {BASE_RESOLUTION} APP_COLOR {APP_COLOR}')


class CorruptedDataError(Exception):
    pass


def resource_name(name):
    return name.lower().replace(' ', '-').replace('_', '-')


import numpy as np
def str2pos(s):
    return np.array(tuple(float(_) for _ in s.split(', ')))


def pos2str(pos):
    logger.info(f'pos2str: {pos}')
    return ', '.join(tuple(str(round(_,2)) for _ in tuple(pos)))


from data.settings import PROFILE
DEV_BUILD = PROFILE.get_setting('misc.dev_build*')
logger.info(f'DEV_BUILD: {"enabled" if DEV_BUILD else "disabled"}')
