from collections import namedtuple as _namedtuple

SpriteBox = _namedtuple('SpriteBox', ['sprite', 'label', 'bg_color', 'fg_color'])
SpriteTitleLabel = _namedtuple('SpriteTitleLabel', ['sprite', 'title', 'label', 'color'])
SpriteLabel = _namedtuple('SpriteLabel', ['sprite', 'text', 'color'])
ProgressBar = _namedtuple('ProgressBar', ['value', 'text', 'color'])

ControlEvent = _namedtuple('ControlEvent', ['name', 'index', 'description'])
KeyboardEvent = _namedtuple('KeyboardEvent', ['keys', 'pos'])
MouseEvent = _namedtuple('MouseEvent', ['button', 'pos'])
