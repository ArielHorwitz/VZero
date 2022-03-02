from collections import namedtuple as _namedtuple

MOUSE_EVENTS = {
    'left': 'select',
    'right': 'activate',
    'middle': 'inspect',
    'scrollup': 'zoomout',
    'scrolldown': 'zoomin',
    'mouse4': 'back',
    'mouse5': 'forward',
}

SpriteBox = _namedtuple('SpriteBox', ['sprite', 'label', 'bg_color', 'fg_color'])
SpriteTitleLabel = _namedtuple('SpriteTitleLabel', ['sprite', 'title', 'label', 'color'])
SpriteLabel = _namedtuple('SpriteLabel', ['sprite', 'text', 'color'])
ProgressBar = _namedtuple('ProgressBar', ['value', 'text', 'color'])

ControlEvent = _namedtuple('ControlEvent', ['name', 'index', 'description'])
InputEvent = _namedtuple('InputEvent', ['name', 'pos', 'description'])
CastEvent = _namedtuple('InputEvent', ['name', 'index', 'pos', 'alt', 'description'])
