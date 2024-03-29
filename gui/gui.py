import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import contextlib
import numpy as np
from functools import partial
from nutil import restart_script
from nutil.kex import widgets
from nutil.time import RateCounter, pingpong
from nutil.vars import Interface, PublishSubscribe
from data import TITLE, FPS, DEV_BUILD, APP_NAME, APP_COLOR, ROOT_DIR, BASE_RESOLUTION
from data.assets import Assets
from data.settings import PROFILE
from gui.home import HomeGUI
from gui.profile import ProfileGUI
from gui.info import HelpGUI
from gui.encounter.encounter import Encounter
from logic import get_api

# Kivy why you warn me for this... BASE_RESOLUTION is not zero and setting window size before mininum doesn't help
widgets.kvWindow.minimum_width, widgets.kvWindow.minimum_height = BASE_RESOLUTION
# "WARNING:kivy:Both Window.minimum_width and Window.minimum_height must be bigger than 0 for the size restriction to take effect."


class App(widgets.App):
    def __init__(self, **kwargs):
        logger.info(f'Initializing GUI @ {FPS} fps.')
        super().__init__(**kwargs)
        self.title = TITLE
        self.icon = str(ROOT_DIR/'icon.png')
        widgets.kvClock.schedule_once(lambda *a: self.__do_startup(), 0)

    def __do_startup(self):
        self.__quit_flag = 0

        self.settings_notifier = PublishSubscribe(name='App settings notifier')
        PROFILE.register_notifications(self._notify_settings)

        self.interface = Interface(name='GUI Home')
        self.home_hotkeys = widgets.InputManager()
        self.enc_hotkeys = widgets.InputManager()
        self.settings_notifier.subscribe('general.enable_hold_key', self.setting_enable_hold_key)
        self.setting_enable_hold_key()
        self.app_hotkeys = widgets.InputManager(app_control_defaults=DEV_BUILD)

        self.game = get_api(self.interface, self.settings_notifier)

        self.switch = self.add(widgets.ScreenSwitch())
        self.home = HomeGUI()
        self.encounter = None
        self.enc_frame = widgets.BoxLayout()
        self.enc_placeholder = widgets.Button(text='No encounter in progress.', on_release=lambda *a: self.switch_screen('home'))
        self.enc_frame.add(self.enc_placeholder)
        self.help = HelpGUI()
        self.profile = ProfileGUI()
        self.switch.add_screen('home', self.home)
        self.switch.add_screen('encounter', self.enc_frame)
        self.switch.add_screen('help', self.help)
        self.switch.add_screen('profile', self.profile)

        # Start mainloop
        self.fps = RateCounter(sample_size=FPS)
        self.hook_mainloop(FPS)

        self.settings_notifier.subscribe('general.fullscreen', self.setting_window_state)
        self.settings_notifier.subscribe('general.fullscreen_type', self.setting_window_state)
        self.settings_notifier.subscribe('general.fullscreen_resolution', self.setting_window_state)
        self.settings_notifier.subscribe('general.window_resolution', self.setting_window_state)
        self.settings_notifier.subscribe('general.window_offset_x', self.setting_window_state)
        self.settings_notifier.subscribe('general.window_offset_y', self.setting_window_state)
        self.settings_notifier.subscribe('general.borderless_offset_x', self.setting_window_state)
        self.settings_notifier.subscribe('general.borderless_offset_y', self.setting_window_state)
        self.settings_notifier.subscribe('general.enable_window_offset', self.setting_window_state)
        self.settings_notifier.subscribe('ui.fullscreen_grab_mouse', self.setting_fullscreen_grab_mouse)
        self.setting_window_state()

        hotkeys = self.make_hotkeys()
        for action, k, c in hotkeys:
            self.settings_notifier.subscribe(f'hotkeys.{action}', self.make_hotkeys)

        if not DEV_BUILD:  # WELCOME SFX
            Assets.play_sfx('ui.welcome', volume='ui')
        self.interface.register('start_encounter', self.start_encounter)
        self.interface.register('end_encounter', self.end_encounter)
        self.interface.register('switch_screen', self.switch_screen)
        self.game.setup()

    def make_hotkeys(self):
        logger.info(f'App making hotkeys...')
        self.app_hotkeys.clear_all(app_control_defaults=DEV_BUILD)
        hotkeys = [
            ('refresh', PROFILE.get_setting('hotkeys.refresh'), lambda *a: self.full_refresh()),
            ('toggle_fullscreen', PROFILE.get_setting('hotkeys.toggle_fullscreen'), lambda *a: PROFILE.toggle_setting('general.fullscreen')),
            ('toggle_detailed', PROFILE.get_setting('hotkeys.toggle_detailed'), lambda *a: PROFILE.toggle_setting('ui.detailed_mode')),
            ('toggle_debug', PROFILE.get_setting('hotkeys.toggle_debug'), lambda *a: PROFILE.toggle_setting('misc.debug_mode')),
            ('tab1', PROFILE.get_setting('hotkeys.tab1'), lambda *a: self.switch_screen('home')),
            ('tab2', PROFILE.get_setting('hotkeys.tab2'), lambda *a: self.switch_screen('encounter')),
            ('tab3', PROFILE.get_setting('hotkeys.tab3'), lambda *a: self.switch_screen('profile')),
            ('tab4', PROFILE.get_setting('hotkeys.tab4'), lambda *a: self.switch_screen('help')),
        ]
        for params in hotkeys:
            self.app_hotkeys.register(*params)
        return hotkeys

    def _notify_settings(self, settings):
        self.settings_notifier.push(settings)
        if self.encounter is not None:
            self.encounter.settings_notifier.push(settings)

    def setting_fullscreen_grab_mouse(self):
        if PROFILE.get_setting('ui.fullscreen_grab_mouse') and PROFILE.get_setting('general.fullscreen'):
            widgets.kvWindow.grab_mouse()
        else:
            widgets.kvWindow.ungrab_mouse()

    def generate_app_control_buttons(self):
        return AppControl(buttons=[
            ('Home', partial(self.switch_screen, 'home')),
            ('Encounter', partial(self.switch_screen, 'encounter')),
            ('Settings', partial(self.switch_screen, 'profile')),
            ('Help', partial(self.switch_screen, 'help')),
        ])

    def full_refresh(self):
        self.offset_window()
        self.settings_notifier.push_all()

    def switch_screen(self, sname):
        if sname == 'encounter' and self.encounter is None:
            sname = 'home'
        logger.info(f'GUI Switch screen to: {sname}')
        self.switch.switch_screen(sname)
        if sname == 'home':
            self.solo_hotkeys(self.home_hotkeys)
        elif sname == 'encounter':
            self.solo_hotkeys(self.enc_hotkeys)
        else:
            self.solo_hotkeys(None)

    def solo_hotkeys(self, hotkeys):
        for hk in {self.home_hotkeys, self.enc_hotkeys}:
            if hk is hotkeys:
                hk.activate()
            else:
                hk.deactivate()

    def setting_window_state(self):
        fullscreen = PROFILE.get_setting('general.fullscreen')
        if fullscreen:
            ftype = PROFILE.get_setting('general.fullscreen_type')
            if ftype == 'borderless':
                self.set_borderless()
            else:
                self.set_fullscreen()
        else:
            self.set_windowed()
        if PROFILE.get_setting('general.enable_window_offset'):
            widgets.kvClock.schedule_once(lambda *a: self.offset_window(), 0)

    def set_windowed(self, *a):
        widgets.kvWindow.fullscreen = False
        widgets.kvWindow.borderless = False
        widgets.kvClock.schedule_once(lambda *a: self.set_window_resolution(), 0)
        widgets.kvWindow.ungrab_mouse()

    def set_borderless(self, *a):
        widgets.kvWindow.fullscreen = False
        widgets.kvWindow.borderless = True
        widgets.kvClock.schedule_once(lambda *a: self.set_window_resolution(fullscreen=True), 0)
        if PROFILE.get_setting('ui.fullscreen_grab_mouse'):
            widgets.kvWindow.grab_mouse()

    def set_fullscreen(self, *a):
        self.set_window_resolution(fullscreen=True)
        widgets.kvWindow.borderless = False
        widgets.kvWindow.fullscreen = True
        if PROFILE.get_setting('ui.fullscreen_grab_mouse'):
            widgets.kvWindow.grab_mouse()

    def set_window_resolution(self, fullscreen=False):
        res = PROFILE.get_setting(f'general.{"fullscreen" if fullscreen else "window"}_resolution')
        widgets.kvWindow.size = tuple(int(_) for _ in res)

    def offset_window(self):
        widgets.kvClock.schedule_once(lambda *a: self._do_offset_window(), 0)

    def _do_offset_window(self):
        if widgets.kvWindow.borderless == False:
            widgets.kvWindow.left = PROFILE.get_setting('general.window_offset_x')
            widgets.kvWindow.top = PROFILE.get_setting('general.window_offset_y')
        else:
            widgets.kvWindow.left = PROFILE.get_setting('general.borderless_offset_x')
            widgets.kvWindow.top = PROFILE.get_setting('general.borderless_offset_y')

    @property
    def fps_color(self):
        return (1, 0, 0, (FPS-self.fps.rate)/45)

    def mainloop_hook(self, dt):
        if self.__quit_flag == 1:
            self.stop()
            return
        elif self.__quit_flag == 2:
            restart_script()
            return
        self.fps.tick()
        s = widgets.kvWindow.size
        self.title = f'{TITLE} | {round(self.fps.rate)} FPS, {s[0]}×{s[1]}'
        self.home.update()
        sname = self.switch.current_screen.name
        if self.encounter is not None and sname == 'encounter':
            self.encounter.update()

    def start_encounter(self, logic_api):
        self.enc_frame.clear_widgets()
        self.encounter = self.enc_frame.add(Encounter(logic_api))
        self.switch_screen('encounter')
        logger.info(f'GUI opened encounter')

    def end_encounter(self):
        self.enc_hotkeys.clear_all()
        self.enc_frame.remove_widget(self.encounter)
        self.enc_frame.add(self.enc_placeholder)
        self.encounter = None
        self.switch_screen('home')
        logger.info(f'GUI closed encounter')

    def do_quit(self):
        self.__quit_flag = 1

    def do_restart(self):
        self.__quit_flag = 2

    def setting_enable_hold_key(self):
        self.enc_hotkeys.block_repeat = not PROFILE.get_setting('general.enable_hold_key')


class AppControl(widgets.AnchorLayout):
    def __init__(self, title=None, buttons=None, **kwargs):
        if title is None:
            title = TITLE
        if buttons is None:
            buttons = []
        super().__init__(**kwargs)
        self.set_size(y=40)
        self.make_bg(APP_COLOR)
        self.center_frame = self.add(widgets.AnchorLayout())
        self.title = self.center_frame.add(widgets.Label(text=title, markup=True))

        # App control buttons
        self.right_frame = self.add(widgets.AnchorLayout(anchor_x='right'))
        app_control_buttons = self.right_frame.add(widgets.BoxLayout())
        sizex = 0
        fbutton = app_control_buttons.add(widgets.Button(text='Fullscreen', on_release=lambda *a: PROFILE.toggle_setting('general.fullscreen')))
        fbutton.set_size(x=100)
        rebutton = app_control_buttons.add(widgets.Button(text=f'Restart', on_release=lambda *a: self.app.do_restart()))
        rebutton.set_size(x=100)
        sizex += 100
        qbutton = app_control_buttons.add(widgets.Button(text='Quit', on_release=lambda *a: self.app.do_quit()))
        qbutton.set_size(x=100)
        sizex += 200
        app_control_buttons.set_size(x=sizex, y=30)

        # Custom buttons
        self.left_frame = self.add(widgets.AnchorLayout(anchor_x='left'))
        self.custom_buttons = self.left_frame.add(widgets.BoxLayout())
        self.custom_buttons.set_size(x=100*len(buttons), y=30)
        for i, (label, callback) in enumerate(buttons):
            btn = widgets.Button(text=label, on_release=lambda *a, c=callback: self.callback(c))
            self.custom_buttons.add(btn)

    def callback(self, c):
        Assets.play_sfx('ui.select', volume='ui')
        c()
