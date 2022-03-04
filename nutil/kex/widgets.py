import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple, defaultdict
import numpy as np

import kivy
from kivy.config import Config as kvConfig
from kivy.app import App as kvApp
from kivy.core.window import Window as kvWindow
from kivy.clock import Clock as kvClock
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
from kivy.uix.scrollview import ScrollView as kvScrollView
from kivy.uix.label import Label as kvLabel
from kivy.uix.button import Button as kvButton
from kivy.uix.spinner import Spinner as kvSpinner
from kivy.uix.checkbox import CheckBox as kvCheckBox
from kivy.uix.dropdown import DropDown as kvDropDown
from kivy.uix.slider import Slider as kvSlider
from kivy.uix.togglebutton import ToggleButton as kvToggleButton
from kivy.uix.progressbar import ProgressBar as kvProgressBar
from kivy.uix.textinput import TextInput as kvTextInput
from kivy.uix.colorpicker import ColorPicker as kvColorPicker
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
from kivy.graphics import Rotate as kvRotate, PushMatrix as kvPushMatrix, PopMatrix as kvPopMatrix
# Audio
from kivy.core.audio import SoundLoader as kvSoundLoader
from kivy.core.audio import Sound as kvSound

import nutil
from nutil.time import ping, pong
from nutil import kex
from nutil.kex import KexWidget


# ABSTRACTIONS
class App(kvApp):
    def __init__(self, escape_exits=False, enable_multitouch=False, **kwargs):
        super().__init__(**kwargs)
        self.root = BoxLayout()
        if escape_exits:
            kex.Config.enable_escape_exit()
        else:
            kex.Config.disable_escape_exit()
        if not enable_multitouch:
            kex.Config.disable_multitouch()
            self.root.bind(
                on_touch_down=self.intercept_multitouch,
                on_touch_up=self.intercept_multitouch,
                on_touch_move=self.intercept_multitouch,
            )

    def run(self, **kwargs):
        super().run(**kwargs)

    def hook_mainloop(self, fps):
        c = lambda *a: kex.Clock.schedule_interval(self.mainloop_hook, 1/fps)
        kex.Clock.schedule_once(c, 0)

    def mainloop_hook(self, dt):
        pass

    def open_settings(self, *args):
        return False

    def set_window_size(self, size):
        kvWindow.size = size

    def toggle_fullscreen(self, *a):
        kvWindow.fullscreen = not kvWindow.fullscreen

    @property
    def add(self):
        return self.root.add

    @property
    def mouse_pos(self):
        return kvWindow.mouse_pos

    def intercept_multitouch(self, w, m):
        if not hasattr(m, 'multitouch_sim'):
            return False
        if m.multitouch_sim:
            return True


class Widget(kvWidget, KexWidget):
    pass


class ConsumeTouch(Widget):
    def __init__(self, enable=True, widget=None, consume_keys=False, **kwargs):
        super().__init__(**kwargs)
        self.enable = enable
        self.widget = widget
        self.consume_keys = consume_keys
        self.__mpos = -1, -1
        self.size = 0, 0
        kvWindow.bind(mouse_pos=self._on_mouse_pos, on_key_down=self.on_key_down)

    def _on_mouse_pos(self, w, p):
        self.__mpos = p

    def on_key_down(self, *a):
        if self.enable and self.consume_keys is True:
            if self.widget is not None:
                r = self.widget.collide_point(*self.__mpos)
                return r
        return False

    def on_touch_down(self, m):
        if not self.enable:
            return False
        if self.widget is not None:
            return self.widget.collide_point(*m.pos)
        return False

    def on_touch_up(self, m):
        if not self.enable:
            return False
        if self.widget is not None:
            return self.widget.collide_point(*m.pos)
        return False

    def on_touch_move(self, m):
        if not self.enable:
            return False
        if self.widget is not None:
            return self.widget.collide_point(*m.pos)
        return False


KeyCalls = namedtuple('KeyCalls', ['keys', 'on_press'])


class InputManager(Widget):
    """
    ^ Control
    ! Alt
    + Shift
    # Super
    """
    MODIFIER_SORT = '^!+#'

    @property
    def actions(self):
        return list(self.__actions.keys())

    def activate(self):
        self.__bound_down = self.keyboard.fbind('on_key_down', self._on_key_down)
        self.__bound_up = self.keyboard.fbind('on_key_up', self._on_key_up)

    def deactivate(self):
        if self.__bound_down:
            self.keyboard.unbind_uid('on_key_down', self.__bound_down)
        if self.__bound_up:
            self.keyboard.unbind_uid('on_key_up', self.__bound_up)
        self.__bound_down = None
        self.__bound_up = None

    def register(self, action, key=None, callback=None):
        if key is not None:
            self.__actions[action].keys.add(key)
            self._refresh_all_keys()
        if callback is not None:
            self.__actions[action].on_press.add(callback)
        logger.info(f'Input manager registering {action}: {self.__actions[action]}')

    def register_callbacks(self, action, callbacks):
        self.__actions[action].on_press.update(callbacks)
        logger.info(f'Input manager registering {action}: {self.__actions[action]}')

    def register_keys(self, action, keys):
        self.__actions[action].keys.update(keys)
        logger.info(f'Input manager registering {action}: {self.__actions[action]}')
        self._refresh_all_keys()

    def remove_actions(self, actions):
        for action in actions:
            if action in self.__actions:
                del self.__actions[action]
        self._refresh_all_keys()

    def remove_action(self, action):
        if action in self.__actions:
            del self.__actions[action]
            self._refresh_all_keys()

    def clear_all(self, app_control_defaults=False):
        self.__actions = defaultdict(lambda: KeyCalls(set(), set()))
        self._refresh_all_keys()
        if app_control_defaults:
            self.register_app_control_defaults()

    def record(self, on_release=None, on_press=None):
        self.__recording_release = on_release
        self.__recording_press = on_press

    def stop_record(self):
        self.record()

    MODIFIERS = {
        'ctrl': '^',
        'alt-gr': '!',
        'alt': '!',
        'shift': '+',
        'super': '#',
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
    KEY2MODIFIER = {
        '^': 'Control',
        '!': 'Alt',
        '+': 'Shift',
        '#': 'Super',
    }

    @property
    def debug_summary(self):
        s = []
        for action, kc in self.__actions.items():
            k = ', '.join(_ for _ in kc.keys)
            s.append(f'{action:<20} «{k}» {kc.on_press}')
        return '\n'.join(s)

    def __init__(self, app_control_defaults=False, **kwargs):
        super().__init__(**kwargs)
        self.__all_keys = set()
        self.__actions = defaultdict(lambda: KeyCalls(set(), set()))
        self.__last_key_code = -1
        self.__last_keys_down = ''
        self.__recording_release = None
        self.__recording_press = None
        self.block_repeat = True
        self.repeat_cooldown = 25
        self.__last_key_down_ping = ping() - self.repeat_cooldown
        self.keyboard = kvWindow.request_keyboard(lambda: None, self)
        self.activate()
        if app_control_defaults is True:
            self.register_app_control_defaults()

    def register_app_control_defaults(self):
        self.register('Debug input', '^!+ f12', lambda *a: self.record(on_release=self.start_debug_record))
        self.register('Restart', '+ escape', lambda *a: self.app.do_restart())
        self.register('Quit', '^+ escape', lambda *a: self.app.do_quit())

    def _refresh_all_keys(self):
        self.__all_keys = set()
        for action, kc in self.__actions.items():
            self.__all_keys.update(kc.keys)

    def _convert_keys(self, modifiers, key_name):
        modifiers = set(self.MODIFIERS[mod] for mod in modifiers)
        if '' in modifiers: modifiers.remove('')
        if len(modifiers) == 0: return key_name
        sorted_modifiers = sorted(modifiers, key=lambda x: self.MODIFIER_SORT.index(x))
        mod_str = ''.join(sorted_modifiers)
        r = f'{mod_str} {key_name}'
        return r

    def _do_calls(self, keys):
        all_callbacks = defaultdict(lambda: set())
        for action, kc in self.__actions.items():
            if keys in kc.keys:
                all_callbacks[action].update(kc.on_press)
        for action in all_callbacks:
            logger.debug(f'InputManager making calls: {all_callbacks[action]}')
            for c in all_callbacks[action]:
                c(action)

    def _on_key_up(self, keyboard, key):
        key_code, key_name = key
        if key_code == self.__last_key_code:
            self.__last_key_code = -1
        if self.__recording_release:
            continue_recording = self.__recording_release(self.__last_keys_down)
            if continue_recording is not True:
                self.record(None, None)
            return
        self.__last_keys_down = ''

    def _on_key_down(self, keyboard, key, key_hex, modifiers):
        key_code, key_name = key
        if key_code == self.__last_key_code:
            if self.block_repeat:
                return
            if pong(self.__last_key_down_ping) < self.repeat_cooldown:
                return
        self.__last_key_down_ping = ping()
        self.__last_key_code = key_code
        self.__last_keys_down = self._convert_keys(modifiers, key_name)
        if self.__recording_press:
            stop_recording = self.__recording_press(self.__last_keys_down)
            if stop_recording is True:
                self.record(None, None)
            return
        if self.__last_keys_down in self.__last_keys_down:
            self._do_calls(self.__last_keys_down)

    def start_debug_record(self, *a):
        logger.info(f'InputManager recording input...')
        kvClock.schedule_once(lambda *a: self.record(on_release=self.debug_record), 1)

    def debug_record(self, keys):
        logger.info(f'InputManager recorded input: <{keys}> ({self.humanize_keys(keys)})')

    @classmethod
    def humanize_keys(cls, keys):
        if ' ' not in keys:
            return keys.capitalize()
        mods, key = keys.split(' ')
        if key in cls.MODIFIERS:
            return key.capitalize()
        dstr = []
        for mod in mods:
            dstr.append(cls.KEY2MODIFIER[mod])
        if key != '' and mods:
            dstr.append(key.capitalize())
        return ' + '.join(dstr)

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


class ScrollView(kvScrollView, KexWidget):
    pass

class ScrollViewNew(kvScrollView, KexWidget):
    SCROLL_SENS = 0.2
    def __init__(self, view, scroll_dir='vertical', **kwargs):
        super().__init__(**kwargs)
        self.scroll_dir = scroll_dir
        self.bar_width = 15
        self.scroll_type = ['bars']
        self.view = self.add(view)
        self.bind(on_touch_down=self._on_touch_down)
        self.bind(size=self.on_size, pos=self.on_size)
        self.view.bind(size=self.on_size, pos=self.on_size)

    @property
    def scroll_dir(self):
        return self.__scroll_dir

    @scroll_dir.setter
    def scroll_dir(self, v):
        self.__scroll_dir = v
        self.do_scroll_x = (v == 'horizontal')
        self.do_scroll_y = (v == 'vertical')

    def on_size(self, *a):
        self.do_scroll_x = self.view.size[0] > self.size[0] and self.scroll_dir == 'horizontal'
        self.do_scroll_y = self.view.size[1] > self.size[1] and self.scroll_dir == 'vertical'

    def _on_touch_down(self, w, m):
        if m.button not in {'scrollup', 'scrolldown'}: return
        if not any((self.do_scroll_x, self.do_scroll_y)): return
        if not self.collide_point(*m.pos): return

        if m.button == 'scrollup':
            if self.scroll_dir == 'horizontal':
                self.scroll_x = min(1, max(0, self.scroll_x + self.SCROLL_SENS))
            elif self.scroll_dir == 'vertical':
                self.scroll_y = min(1, max(0, self.scroll_y - self.SCROLL_SENS))
        elif m.button == 'scrolldown':
            if self.scroll_dir == 'horizontal':
                self.scroll_x = min(1, max(0, self.scroll_x - self.SCROLL_SENS))
            elif self.scroll_dir == 'vertical':
                self.scroll_y = min(1, max(0, self.scroll_y + self.SCROLL_SENS))


# BASIC WIDGETS
class Label(kvLabel, KexWidget):
    def __init__(self, *a, halign='center', valign='center', **k):
        super().__init__(*a, halign=halign, valign=valign, **k)
        self.bind(size=self._on_resize)

    def _on_resize(self, *a):
        self.text_size = self.size


class Button(kvButton, KexWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = 0.6, 0.6, 0.6, 1

    def on_touch_down(self, m):
        if m.button != 'left':
            return
        return super().on_touch_down(m)


class Spinner(kvSpinner, KexWidget):
    pass


class CheckBox(kvCheckBox, KexWidget):
    pass


class ToggleButton(kvToggleButton, KexWidget):
    @property
    def active(self):
        return self.state == 'down'

    @active.setter
    def active(self, x):
        self.state = 'down' if x else 'normal'


class Slider(kvSlider, KexWidget):
    def __init__(self, on_value=None, range=(0,1), step=0.01, **kwargs):
        super().__init__(range=range, step=step, **kwargs)
        self.__on_value = on_value
        if callable(on_value):
            self.__mouse_hold = False
            self.bind(on_touch_down=self._on_touch_down, on_touch_up=self._on_touch_up)

    def _on_touch_down(self, w, m):
        if self.__on_value is None:
            return False
        if not self.collide_point(*m.pos):
            return False
        self.__mouse_hold = True

    def _on_touch_up(self, w, m):
        if self.__mouse_hold is True:
            self.__mouse_hold = False
            return self.__on_value(self.value)
        return False


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


class DropDownFrame(kvDropDown, KexWidget):
    pass


class DropDownSelect(Button):
    def __init__(self, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert callable(callback)
        self.callback = callback
        self.dropdown = DropDownFrame()
        self.dropdown.make_bg((0,0,0,0.75))
        self.bind(on_release=self.dropdown.open)

    def invoke_option(self, index, label):
        self.text = label
        self.callback(index, label)
        self.dropdown.dismiss()

    def set_options(self, options):
        for index, label in enumerate(options):
            btn = Button(text=label)
            btn.set_size(y=40)
            btn.bind(on_release=lambda w, i=index, l=label: self.invoke_option(i, l))
            self.dropdown.add_widget(btn)


class ColorSelect(kvLabel, KexWidget):
    def __init__(self, callback, size=(300, 300), *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert callable(callback)
        self.callback = callback
        self.dropdown = kvDropDown(auto_width=False)
        self.bind(on_touch_down=self._on_touch_down)
        self.picker = ColorPick(callback=self._callback)
        self.picker.set_size(*size)
        self.dropdown.add_widget(self.picker)
        kex.set_size(self.dropdown, *size)

    def _on_touch_down(self, w, m):
        if m.button != 'left' or not self.collide_point(*m.pos):
            return False
        self.dropdown.open(w)

    def _callback(self, color):
        self.callback(color)
        self.make_bg(color)
        self.text = ', '.join(f'{round(_*255)}' for _ in color)

    def set_color(self, color, set_text=True):
        self.picker.set_color(color)
        self.make_bg(color)
        self.text = ', '.join(f'{round(_*255)}' for _ in color)


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
            self.set_size(y=35)
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
        self.bind(pos=self.reposition, size=self.reposition)

    def add_screen(self, sname, view):
        new_screen = self.add(Screen(name=sname))
        new_screen.view = view
        new_screen.add(view)
        return new_screen

    def switch_screen(self, sname):
        self.current = sname

    def reposition(self, *a):
        # Uh... Kivy?
        # If the manager isn't showing (e.g. when part of a non-showing screen
        # in another screen manager), and then it shows, it will trigger on_pos
        # for itself but not for it's current screen? Only when the screen
        # is switched to will kivy reposition.
        self.current_screen.pos = self.pos
        self.current_screen.size = self.size  # Haven't tested if required, but adding for good measure


class Screen(kvScreen, KexWidget):
    pass


class Progress(Widget):
    def __init__(self,
            source=None,
            bg_color=(0, 0, 0, 1),
            fg_color=(1, 0, 1, 1),
            text='',
            **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            self._bg_color = kvColor()
            self._bg_rect = kvRectangle(pos=self.pos, size=self.size)
            self._fg_color = kvColor()
            self._fg_rect = kvRectangle(source=source, pos=self.pos, size=(0, 0))
        self._label = self.add(Label(halign='center', valign='middle'))

        self.bg_color = bg_color
        self.fg_color = fg_color
        self.progress = 0
        self.text = text

        self.bind(pos=self.reposition, size=self.reposition)

    @property
    def bg_color(self):
        return self.__bg_color

    @property
    def fg_color(self):
        return self.__fg_color

    @property
    def progress(self):
        return self.__progress

    @property
    def text(self):
        return self.__text

    @bg_color.setter
    def bg_color(self, x):
        self.__bg_color = x
        self._bg_color.rgba = self.__bg_color

    @fg_color.setter
    def fg_color(self, x):
        self.__fg_color = x
        self._fg_color.rgba = self.__fg_color

    @progress.setter
    def progress(self, x):
        self.__progress = x
        self._fg_rect.size = self.size[0]*self.__progress, self.size[1]

    @text.setter
    def text(self, x):
        self.__text = x
        self._label.text = self.__text

    def reposition(self, *args):
        self._fg_rect.pos = self.pos
        self._fg_rect.size = self.size[0]*self.__progress, self.size[1]
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._label.pos = self.pos
        self._label.size = self.size
        self._label.text_size = self.size


class ColorPick(GridLayout):
    def __init__(self, callback, *args, **kwargs):
        super().__init__(*args, cols=2, **kwargs)
        assert callable(callback)
        self.callback = callback
        self.add(Label(text='R')).set_size(x=30)
        self.r = self.add(Slider(on_value=self._on_color))
        self.add(Label(text='G')).set_size(x=30)
        self.g = self.add(Slider(on_value=self._on_color))
        self.add(Label(text='B')).set_size(x=30)
        self.b = self.add(Slider(on_value=self._on_color))
        self.add(Label(text='A')).set_size(x=30)
        self.a = self.add(Slider(on_value=self._on_color))
        self.__color = 0, 0, 0, 0

    @property
    def color(self):
        return self.__color

    def set_color(self, color):
        self.__color = color
        self.r.value, self.g.value, self.b.value, self.a.value = color
        self.make_bg(color)

    def _on_color(self, *a):
        self.__color = self.r.value, self.g.value, self.b.value, self.a.value
        self.make_bg(self.__color)
        self.callback(self.__color)


def text_texture(text, font_size=16):
    label = CoreLabel(text=text, font_size=font_size)
    label.refresh()
    texture = label.texture
    texture_size = texture.size
    return texture
