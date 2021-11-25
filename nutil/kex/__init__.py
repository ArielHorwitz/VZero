
import enum
import kivy
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.config import Config as kvConfig
from kivy.graphics import Color, Rectangle

import numpy as np
import nutil.vars
from nutil.random import Seed, SEED

import logging
logger = logging.getLogger(__name__)


DEFAULT_BG_COLOR = (Seed().r, 1, 0.25)
LINE_DP = 35
LINE_DP_STR = f'{LINE_DP}dp'


class KexWidget:
    def make_bg(self, *args, **kwargs):
        return make_bg(self, *args, **kwargs)

    def _update_bg(self, *args, **kwargs):
        return _update_bg(self, *args, **kwargs)

    def add(self, *args, **kwargs):
        if 'index' in kwargs:
            if kwargs['index'] == -1:
                kwargs['index'] = len(self.children)
        return add(self, *args, **kwargs)

    def set_size(self, *args, **kwargs):
        return set_size(self, *args, **kwargs)

    def bind(self, *args, **kwargs):
        super().bind(*args, **kwargs)
        return self

    @property
    def is_root_descendant(self):
        w = self
        while w.parent:
            if self.parent is self.app.root:
                return True
            w = w.parent
        return False

    @property
    def get_root_screen(self):
        w = self
        while not isinstance(self, BaseWidgets.Screen):
            w = w.parent
        return w

    @property
    def bg_color(self):
        return self._bg_color.hsv

    @property
    def app(self):
        return kivy.app.App.get_running_app()


def after_next_frame(f):
    Clock.schedule_once(f, 0)

def schedule(f, t):
    Clock.schedule_once(f, t)

def set_size(widget, x=None, y=None, hx=1, hy=1):
    hx = hx if x is None else None
    hy = hy if y is None else None
    x = widget.width if x is None else x
    y = widget.height if y is None else y

    widget.size_hint = (hx, hy)
    widget.size = (x, y)
    return widget

def add(parent, child, *args, reverse_index=None, **kwargs):
    if reverse_index is not None:
        kwargs['index'] = len(parent.children) - reverse_index
    parent.add_widget(child, *args, **kwargs)
    return child

def _update_bg(widget, *args):
    widget._bg.pos = widget.pos
    widget._bg.size = widget.size

def make_bg(widget, color=None):
    if color is None:
        color = random_color()
    if hasattr(widget, '_bg'):
        if widget._bg_color is None:
            raise RuntimeError(f'widget {widget} has _bg but no _bg_color')
        if not isinstance(widget._bg_color, Color):
            raise RuntimeError(f'widget {widget} _bg_color is not a Color instruction')
        if len(color) == 3:
            color = (*color, 1)
        widget._bg_color.rgba = color
        return color
    with widget.canvas.before:
        widget._bg_color = Color(*color)
        widget._bg = Rectangle(size=widget.size, pos=widget.pos)
        widget.bind(pos=widget._update_bg, size=widget._update_bg)
    return color

def random_color(v=1, a=1):
    return list(np.array(tuple(SEED.r for _ in range(3)))*v)+[a]

def alternate_color(color, drift=1/2):
    r = list((_+drift)%1 for _ in color[:3])
    a = 1
    if len(color) == 4:
        r.append(color[3])
    return r

def set_focus(w, delay=0.05):
    if delay:
        Clock.schedule_once(lambda w=w: _do_set_focus(w), delay)
    else:
        _do_set_focus(w)

def _do_set_focus(w):
    w.focus = True

modify_color = nutil.vars.modify_color

class Config:
    @staticmethod
    def disable_escape_exit():
        kvConfig.set('kivy', 'exit_on_escape', '0')
        logger.info('Disabled escape key exit.')

    @staticmethod
    def enable_escape_exit():
        kvConfig.set('kivy', 'exit_on_escape', '1')
        logger.info('Enabled escape key exit.')

    @staticmethod
    def disable_multitouch():
        kvConfig.set('input', 'mouse', 'mouse,disable_multitouch')
        logger.info('Disabled multitouch.')
