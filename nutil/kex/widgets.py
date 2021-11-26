import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import numpy as np

import kivy
from kivy.app import App as kvApp
from kivy.core.window import Window as kvWindow
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.uix.behaviors.button import ButtonBehavior as kvButtonBehavior
from kivy.uix.behaviors.drag import DragBehavior as kvDragBehavior
from kivy.core.clipboard import Clipboard
# Widgets
from kivy.uix.widget import Widget as kvWidget
from kivy.uix.boxlayout import BoxLayout as kvBoxLayout
from kivy.uix.gridlayout import GridLayout as kvGridLayout
from kivy.uix.stacklayout import StackLayout as kvStackLayout
from kivy.uix.floatlayout import FloatLayout as kvFloatLayout
from kivy.uix.anchorlayout import AnchorLayout as kvAnchorLayout
from kivy.uix.relativelayout import RelativeLayout as kvRelativeLayout
from kivy.uix.label import Label as kvLabel
from kivy.uix.button import Button as kvButton
from kivy.uix.spinner import Spinner as kvSpinner
from kivy.uix.checkbox import CheckBox as kvCheckBox
from kivy.uix.slider import Slider as kvSlider
from kivy.uix.progressbar import ProgressBar as kvProgressBar
from kivy.uix.textinput import TextInput as kvTextInput
from kivy.uix.image import Image as kvImage
# Animation
from kivy.uix.screenmanager import ScreenManager as kvScreenManager
from kivy.uix.screenmanager import Screen as kvScreen
from kivy.uix.screenmanager import FadeTransition as kvFadeTransition
from kivy.uix.screenmanager import CardTransition as kvCardTransition
from kivy.uix.screenmanager import SlideTransition as kvSlideTransition
from kivy.uix.screenmanager import SwapTransition as kvSwapTransition
from kivy.uix.screenmanager import WipeTransition as kvWipeTransition
from kivy.uix.screenmanager import ShaderTransition as kvShaderTransition
from kivy.uix.modalview import ModalView as kvModalView
# Graphics
from kivy.graphics.instructions import InstructionGroup as kvInstructionGroup
from kivy.graphics import Color as kvColor
from kivy.graphics import Rectangle as kvRectangle
from kivy.graphics import Line as kvLine
from kivy.graphics import Point as kvPoint
from kivy.graphics import Ellipse as kvEllipse
from kivy.graphics import Quad as kvQuad
from kivy.graphics import Triangle as kvTriangle
from kivy.graphics import Bezier as kvBezier
from kivy.graphics import Rotate as kvRotate
# Audio
from kivy.core.audio import SoundLoader as kvSoundLoader
from kivy.core.audio import Sound as kvSound

import nutil
from nutil import display as ndis
from nutil import kex
from nutil.kex import KexWidget


# ABSTRACTIONS
class App(kvApp):
    def __init__(self, make_menu=True, make_bg=True,
                 escape_exits=False, enable_multitouch=False,
                 **kwargs):
        super().__init__(**kwargs)
        self.__mouse_pos = (0, 0)
        kvWindow.bind(mouse_pos=self._on_mouse_pos)
        if escape_exits:
            kex.Config.enable_escape_exit()
        else:
            kex.Config.disable_escape_exit()
        if not enable_multitouch:
            kex.Config.disable_multitouch()
        self.root = BoxLayout()
        if make_bg:
            self.root.make_bg((*kex.random_color()[:3], 0.2))
        if make_menu:
            self.root.orientation = 'vertical'
            self.menu = self.add(Menu(add_quit_buttons=True))
        self.hotkeys = Hotkeys(self.root)

    def run(self, **kwargs):
        super().run(**kwargs)

    def hook_mainloop(self, fps):
        kex.Clock.schedule_interval(self.mainloop_hook, 1/fps)

    def mainloop_hook(self, dt):
        pass

    def open_settings(self, *args):
        return False

    def set_window_size(self, size):
        kvWindow.size = size

    def toggle_fullscreen(self, *a):
        kvWindow.fullscreen = not kvWindow.fullscreen

    def _on_mouse_pos(self, w, p):
        self.__mouse_pos = p

    @property
    def add(self):
        return self.root.add

    @property
    def mouse_pos(self):
        return self.__mouse_pos


class Hotkeys:
    """
    ^ Control
    ! Alt
    + Shift
    # Super
    """
    HotkeyAction = collections.namedtuple('HotkeyAction', ['keys', 'calls'])
    MODIFIERS = {
        'ctrl': '^',
        'alt': '!',
        'shift': '+',
        'meta': '#',
        'control': '^',
        'lctrl': '^',
        'rctrl': '^',
        'lalt': '!',
        'ralt': '!',
        'lshift': '+',
        'rshift': '+',
        'numlock': '',
        'capslock': '',
        }
    MODIFIER_SORT = '^!+#'
    def __init__(self, root, default_hotkeys=True):
        DEFAULT_HOTKEYS = [
            ('Debug hotkeys', '^+ f9', self.print_hotkeys),
            ('Restart', '+ escape', nutil.restart_script),
            ('Quit', '^+ escape', lambda *a: quit()),
        ]
        self.__all_keys = set()
        self.actions = {}
        if default_hotkeys:
            for _ in DEFAULT_HOTKEYS:
                self.register(*_)
        self.keyboard = kvWindow.request_keyboard(self.keyboard_released, root)
        self.keyboard.bind(on_key_down=self.on_key_down)

    def print_hotkeys(self):
        s = []
        for name, (keys, calls) in self.actions.items():
            ks = []
            for k in keys:
                mods, key_ = k.split(" ") if ' ' in k else ('', k)
                ks.append(f'{mods:>3} {key_:<7}')
            s.append(f'<{" ¦ ".join(ks)}> {name:<30} ({len(calls)} calls: {calls})')
        m = ndis.make_title(f'Hotkeys Debug')+ndis.njoin(s)
        print(m)
        logger.debug(m)
        return s

    def convert_keys(self, modifiers, key_name):
        if len(modifiers) == 0:
            return f'{key_name}'
        modifiers = tuple(Hotkeys.MODIFIERS[mod] for mod in modifiers)
        sorted_modifiers = sorted(modifiers, key=lambda x: Hotkeys.MODIFIER_SORT.index(x))
        mod_str = ndis.njoin(sorted_modifiers, split='')
        if not mod_str == '':
            mod_str += ' '
        r = f'{mod_str}{key_name}'
        return r

    def check_keys(self, keys):
        if keys in self.__all_keys:
            calls = set()
            for aname, action in self.actions.items():
                if keys in action.keys:
                    logger.debug(f'Found action: {aname}')
                    for call in action.calls:
                        calls.add(call)
            for call in calls:
                call()
            return True
        else:
            return False

    def register_dict(self, d):
        for action, (keys, calls) in d.items():
            self.register(action, keys, calls)

    def register(self, action, keys=None, calls=None):
        calls = set() if calls is None else calls
        keys = set() if keys is None else keys
        if not isinstance(keys, set):
            keys = {keys}
        if not isinstance(calls, set):
            calls = {calls}
        if action not in self.actions:
            self.actions[action] = Hotkeys.HotkeyAction(keys=set(), calls=set())
        action = self.actions[action]
        action.keys.update(keys)
        self.__all_keys.update(keys)
        action.calls.update(calls)

    def keyboard_released(self, *args):
        logger.debug(f'Hotkeys keyboard_released args: {ndis.strfy(args)}')

    def on_key_down(self, keyboard, key, key_hex, modifiers):
        key_code, key_name = key
        keys = self.convert_keys(modifiers, key_name)
        logger.debug(f'Key down: {modifiers} + <{key_name}> ({key_code}) | «{keys}»')
        found = self.check_keys(keys)

    def on_key_up(self, keyboard, key):
        key_code, key_name = key
        logger.debug(f'Key up: {key_name} ({key_code})')


class Widget(kvWidget, KexWidget):
    pass

# LAYOUTS
class BoxLayout(kvBoxLayout, KexWidget):
    def split(self, count=2, orientation=None):
        if orientation:
            self.orientation = orientation
        return (self.add(BoxLayout()) for _ in range(count))

class GridLayout(kvGridLayout, KexWidget):
    pass

class AnchorLayout(kvAnchorLayout, KexWidget):
    pass

class StackLayout(kvStackLayout, KexWidget):
    pass

class RelativeLayout(kvStackLayout, KexWidget):
    pass

class ModalView(kvModalView, KexWidget):
    pass

# BASIC WIDGETS
class Label(kvLabel, KexWidget):
    pass


class Button(kvButton, KexWidget):
    pass


class Spinner(kvSpinner, KexWidget):
    pass


class CheckBox(kvCheckBox, KexWidget):
    pass


class Slider(kvSlider, KexWidget):
    pass


class ListBox(BoxLayout, KexWidget):
    def __init__(self, *args, bg_color=None, **kwargs):
        super().__init__(*args, orientation='vertical', **kwargs)
        self.color1 = kex.random_color(v=0.25) if bg_color is None else bg_color
        self.color2 = kex.alternate_color(self.color1)

    def add_item(self, item):
        item.make_bg(color=self.get_alternating_color())
        return self.add(item)

    def get_alternating_color(self):
        return self.color1 if len(self.children) % 2 == 0 else self.color2


# INPUT WIDGETS
class Entry(kvTextInput, KexWidget):
    def __init__(
            self, on_text=None,
            on_text_delay=0,
            defocus_on_validate=True,
            background_color=(1, 1, 1, 0.2),
            foreground_color=(1, 1, 1, 1),
            tab_focus=True,
            multiline=False,
            **kwargs):
        self.__on_text = None
        self.__on_text_delay = on_text_delay
        self.__tab_focus = tab_focus
        if callable(on_text):
            self.__on_text = on_text
            # if 'on_text_validate' not in kwargs:
            #     kwargs['on_text_validate'] = self.__on_text
        super().__init__(
            background_color=background_color,
            foreground_color=foreground_color,
            multiline=multiline, **kwargs)
        if not multiline:
            self.set_size(y=kex.LINE_DP_STR)
        self.text_validate_unfocus = defocus_on_validate

    def keyboard_on_key_down(self, win, keycode, text, modifiers):
        """Overwrites the tab and shift tab keys, as they are expected to be used to switch widget focus."""
        if self.__tab_focus:
            if keycode[1] == 'tab' and modifiers == []:
                if self.focus_next:
                    kex.set_focus(self.focus_next)
            elif keycode[1] == 'tab' and modifiers == ['shift']:
                if self.focus_previous:
                    kex.set_focus(self.focus_previous)
            else:
                super().keyboard_on_key_down(win, keycode, text, modifiers)
        else:
            super().keyboard_on_key_down(win, keycode, text, modifiers)

    def set_focus(self, focus=True):
        kex.Clock.schedule_once(self.entry_focus, 0.05)

    def entry_focus(self, *args):
        self.focus = True

    def __on_text_call(self):
        if callable(self.__on_text):
            kex.Clock.schedule_once(lambda dt: self.__on_text(self.text), self.__on_text_delay)

    def delete_selection(self, *args, **kwargs):
        super().delete_selection(*args, **kwargs)
        self.__on_text_call()

    def insert_text(self, *args, **kwargs):
        super().insert_text(*args, **kwargs)
        self.__on_text_call()

    def _refresh_text(self, *args, **kwargs):
        super()._refresh_text(*args, **kwargs)
        self.__on_text_call()

    def _on_textinput_focused(self, *args, **kwargs):
        value = args[1]
        super()._on_textinput_focused(*args, **kwargs)
        if value:
            self.select_all()


class Image(kvImage, KexWidget):
    pass


# PREMADE WIDGETS
class Menu(BoxLayout):
    def __init__(self, buttons=None, add_quit_buttons=True, **kwargs):
        super().__init__(**kwargs)
        self.set_size(y=kex.LINE_DP_STR)
        if add_quit_buttons:
            self.add(Button(text='Restart', on_release=lambda *a: nutil.restart_script()))
            self.add(Button(text='Quit', on_release=lambda *a: quit()))


class Sound:
    @classmethod
    def load(cls, filename, *a, **kw):
        return cls(kvSoundLoader.load(str(filename)), *a, **kw)

    def __init__(self, s, volume=1, loop=False, pitch=1):
        self.__sound = s
        self.__sound.volume = volume
        self.__sound.loop = loop
        self.__sound.pitch = pitch
        self.__last_pos = None

    @property
    def sound(self):
        return self.__sound

    def set_volume(self, volume=1):
        self.__sound.volume = volume

    def play(self, volume=None, loop=False, replay=True):
        self.__sound.loop = loop
        if not replay and self.__sound.get_pos() != 0:
            return None
        if replay and self.__sound.get_pos() != 0:
            self.__sound.stop()
        if volume is not None:
            self.__sound.volume = volume
        r = self.__sound.play()
        if self.__last_pos is not None and self.__last_pos != 0:
            self.__sound.seek(self.__last_pos)
        return r

    def stop(self, *a, **k):
        self.__last_pos = None
        return self.__sound.stop(*a, **k)

    def pause(self):
        if self.__sound.state != 'play':
            return
        self.__last_pos = self.__sound.get_pos()
        self.__sound.stop()


class ScreenSwitch(kvScreenManager, KexWidget):
    def __init__(self, screens=None, transition=None, **kwargs):
        transition = kvFadeTransition(duration=0) if transition is None else transition
        super().__init__(transition=transition, **kwargs)
        self._screens = []
        if screens is not None:
            for screen_name in screens:
                self.add_screen(screen_name)

    def add_screen(self, sname, view=None):
        new_screen = self.add(Screen(name=sname))
        if view is not None:
            view = new_screen.add(view)
        self._screens.append(new_screen)
        return new_screen

    def switch_screen(self, sname, *args, **kwargs):
        self.switch_to(self.get_screen(sname), *args, **kwargs)


class Screen(kvScreen, KexWidget):
    pass


class Progress(Widget):
    def __init__(self,
            bg_color=(0, 0, 0), fg_color=(1, 0, 1),
            **kwargs):
        super().__init__(**kwargs)
        self.__bg_color = bg_color
        self.__fg_color = fg_color
        self.__progress = 0
        self.__text = None

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, x):
        self.__text = x
        self.draw_instructions()

    @property
    def bg_color(self):
        return self.__bg_color

    @bg_color.setter
    def bg_color(self, x):
        self.__bg_color = x
        self.draw_instructions()

    @property
    def fg_color(self):
        return self.__fg_color

    @fg_color.setter
    def fg_color(self, x):
        self.__fg_color = x
        self.draw_instructions()

    @property
    def progress(self):
        return self.__progress

    @progress.setter
    def progress(self, x):
        self.__progress = x
        self.draw_instructions()

    def draw_instructions(self):
        self.canvas.clear()
        with self.canvas:
            kvColor(*self.__bg_color)
            kvRectangle(pos=self.pos, size=self.size)
            kvColor(*self.__fg_color)
            progress_size = self.size[0]*self.__progress, self.size[1]
            kvRectangle(pos=self.pos, size=progress_size)
            kvColor(1, 1, 1)
            if self.__text is not None:
                texture = text_texture(self.__text)
                kvRectangle(pos=(self.pos[0]+5, self.pos[1]), size=texture.size, texture=texture)


def text_texture(text, font_size=16):
    label = CoreLabel(text=text, font_size=font_size)
    label.refresh()
    return label.texture
