import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import contextlib
import numpy as np
from functools import partial
from pathlib import Path
from nutil import restart_script
from nutil.kex import widgets
from nutil.time import RateCounter, pingpong
from nutil.vars import Interface
from data import TITLE, FPS, DEV_BUILD, APP_NAME, APP_COLOR
from data.assets import Assets
from data.settings import Settings
from gui.home import HomeGUI
from gui.profile import ProfileGUI
from gui.info import HelpGUI
from gui.encounter.encounter import Encounter
from logic import get_api


class App(widgets.App):
    def __init__(self, **kwargs):
        logger.info(f'Initializing GUI @ {FPS} fps.')
        super().__init__(make_bg=False, make_menu=False, **kwargs)
        self.__quit_flag = 0
        self.interface = Interface(name='GUI Home')
        self.home_hotkeys = widgets.InputManager()
        self.enc_hotkeys = widgets.InputManager()
        self.enc_hotkeys.block_repeat = not Settings.get_setting('enable_hold_key', 'General')
        self.app_hotkeys = widgets.InputManager(app_control_defaults=True)
        self.icon = str(Path.cwd()/'icon.png')

        self.game = get_api(self.interface)

        self.switch = self.add(widgets.ScreenSwitch())
        self.home = HomeGUI()
        self.encounter = None
        self.enc_frame = widgets.BoxLayout()
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

        widgets.kvWindow.size = self.configured_resolution(full=False)
        default_window_state = Settings.get_setting('default_window', 'General')
        if default_window_state == 'fullscreen':
            widgets.kvClock.schedule_once(lambda *a: self.toggle_window_fullscreen(True), 0)
        elif default_window_state == 'borderless':
            widgets.kvClock.schedule_once(lambda *a: self.toggle_window_borderless(True), 0)
        else:
            widgets.kvClock.schedule_once(lambda *a: self.toggle_window_borderless(False), 0)

        for params in [
            ('Refresh', Settings.get_setting('refresh', 'Hotkeys'), lambda *a: self.full_refresh()),
            ('Fullscreen', Settings.get_setting('toggle_fullscreen', 'Hotkeys'), lambda *a: self.toggle_window_fullscreen()),
            ('Borderless', Settings.get_setting('toggle_borderless', 'Hotkeys'), lambda *a: self.toggle_window_borderless()),
            ('Tab: Home', '^+ f1', lambda *a: self.switch_screen('home')),
            ('Tab: Encounter', '^+ f2', lambda *a: self.switch_screen('encounter')),
            ('Tab: Settings', '^+ f3', lambda *a: self.switch_screen('profile')),
            ('Tab: Help', '^+ f4', lambda *a: self.switch_screen('help')),
        ]:
            self.app_hotkeys.register(*params)
        if not DEV_BUILD:
            Assets.play_sfx('ui.welcome', volume='ui')
        self.interface.register('start_encounter', self.start_encounter)
        self.interface.register('end_encounter', self.end_encounter)
        self.interface.register('full_refresh', self.full_refresh)
        self.interface.register('switch_screen', self.switch_screen)
        self.game.setup()

    def generate_app_control_buttons(self):
        return AppControl(buttons=[
            ('Home', partial(self.switch_screen, 'home')),
            ('Encounter', partial(self.switch_screen, 'encounter')),
            ('Settings', partial(self.switch_screen, 'profile')),
            ('Help', partial(self.switch_screen, 'help')),
        ])

    def full_refresh(self):
        Settings.reload_settings()
        self.switch_screen(self.switch.current_screen.name)

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

    def toggle_window_borderless(self, set_as=None):
        if widgets.kvWindow.fullscreen:
            self.toggle_window_fullscreen(set_as=False)
            return
        set_as = not widgets.kvWindow.borderless if set_as is None else set_as
        logger.info(f'Setting borderless: {set_as}')
        if set_as is True:
            widgets.kvWindow.borderless = True
            widgets.kvClock.schedule_once(lambda *a: widgets.kvWindow.maximize(), 0)
        else:
            pos = np.array([widgets.kvWindow.left, widgets.kvWindow.top])
            center = pos + (np.array(widgets.kvWindow.size) / 2)
            widgets.kvWindow.borderless = False
            widgets.kvWindow.restore()
            widgets.kvWindow.size = self.configured_resolution(full=False)
            new_pos = center - (np.array(widgets.kvWindow.size) / 2)
            new_pos[new_pos<50] = 50
            new_pos[new_pos>600] = 600
            widgets.kvWindow.left = int(new_pos[0])
            widgets.kvWindow.top = int(new_pos[1])

    def toggle_window_fullscreen(self, set_as=None):
        set_as = not widgets.kvWindow.fullscreen if set_as is None else set_as
        logger.info(f'Setting fullscreen: {set_as}')
        if set_as is True:
            widgets.kvWindow.size = self.configured_resolution(full=True)
            widgets.kvWindow.fullscreen = True
        else:
            widgets.kvWindow.fullscreen = False
            widgets.kvClock.schedule_once(lambda *a: self.toggle_window_borderless(False))

    def configured_resolution(self, full=True):
        raw_resolution = Settings.get_setting('full_resolution' if full else 'window_resolution', 'General')
        return tuple(int(_) for _ in raw_resolution)

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
        self.full_refresh()

    def end_encounter(self):
        self.enc_hotkeys.clear_all()
        self.enc_frame.remove_widget(self.encounter)
        self.enc_frame.add(self.enc_placeholder)
        self.encounter = None
        self.switch_screen('home')
        logger.info(f'GUI closed encounter')
        self.full_refresh()

    def do_quit(self):
        self.__quit_flag = 1

    def do_restart(self):
        self.__quit_flag = 2


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
        if DEV_BUILD:
            rebutton = app_control_buttons.add(widgets.Button(text=f'Restart {APP_NAME}', on_release=lambda *a: self.app.do_restart()))
            rebutton.set_size(x=150)
            sizex += 150
        qbutton = app_control_buttons.add(widgets.Button(text='Quit', on_release=lambda *a: self.app.do_quit()))
        qbutton.set_size(x=100)
        sizex += 100
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
