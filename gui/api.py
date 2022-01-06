from collections import namedtuple

SpriteBox = namedtuple('SpriteBox', ['sprite', 'label', 'bg_color', 'fg_color'])
SpriteTitleLabel = namedtuple('SpriteTitleLabel', ['sprite', 'title', 'label', 'color'])
SpriteLabel = namedtuple('SpriteLabel', ['sprite', 'text', 'color'])
ProgressBar = namedtuple('ProgressBar', ['value', 'text', 'color'])
