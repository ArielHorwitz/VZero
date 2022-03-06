
VERSION = 0.017
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
[b]© 2021-2022, all rights reserved by Ariel Horwitz.[/b]
Redistribution of this software is prohibited without explicit written permission.
~
Written in python with kivy (https://github.com/kivy/kivy).
~
A special thanks to [b]Yisrael Hessler[/b] for providing a great deal of testing and feedback.
--- Art
[b]Yisrael Hessler[/b] - https://github.com/imcrazeegamer
[b]Orr Didi[/b] - https://scardust.co
[b]Kenney[/b] - https://kenney.itch.io/
[b]7Soul1[/b] - https://www.deviantart.com/7soul1
[b]Dungeon Crawl Stone Soup[/b] - https://opengameart.org/content/dungeon-crawl-32x32-tiles
And many more public domain contributions discovered on https://OpenGameArt.org
~
While there are many public domain contributions, redistribution of [i]proprietary[/i] artwork is prohibited without explicit written permission.
"""


class CorruptedDataError(Exception):
    pass


def resource_name(name):
    return name.lower().replace(' ', '-').replace('_', '-')


import numpy as np
def str2pos(s):
    return np.array(tuple(float(_) for _ in s.split(', ')))


def pos2str(pos):
    return ', '.join(tuple(str(round(_,2)) for _ in tuple(pos)))
