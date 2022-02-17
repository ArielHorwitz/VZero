import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import contextlib
import numpy as np
from pathlib import Path
import nutil
from nutil.kex import widgets
from nutil.time import RateCounter, pingpong
from data import TITLE, FPS, DEV_BUILD
from data.assets import Assets
from data.settings import Settings
from gui.home import HomeGUI
from gui.encounter.encounter import Encounter
from engine import get_api


class App(widgets.App):
    def __init__(self, **kwargs):
        logger.info(f'Initializing GUI @ {FPS} fps.')
        super().__init__(make_bg=False, make_menu=False, **kwargs)
        self.home_hotkeys = widgets.InputManager()
        self.enc_hotkeys = widgets.InputManager()
        self.enc_hotkeys.block_repeat = not Settings.get_setting('enable_hold_key', 'General')
        self.app_hotkeys = widgets.InputManager()
        self.icon = str(Path.cwd()/'icon.png')

        self.game = get_api()

        self.switch = self.add(widgets.ScreenSwitch())
        self.home = HomeGUI()
        self.encounter = None
        self.enc_frame = widgets.BoxLayout()
        self.enc_frame.add(ENC_PLACEHOLDER)
        self.info1 = INFO_PANEL1
        self.info2 = INFO_PANEL2
        self.switch.add_screen('home', self.home)
        self.switch.add_screen('enc', self.enc_frame)
        self.switch.add_screen('info1', self.info1)
        self.switch.add_screen('info2', self.info2)

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
            ('Fullscreen', Settings.get_setting('toggle_fullscreen', 'Hotkeys'), lambda *a: self.toggle_window_fullscreen()),
            ('Borderless', Settings.get_setting('toggle_borderless', 'Hotkeys'), lambda *a: self.toggle_window_borderless()),
            ('Tab: Home', '^+ f1', lambda *a: self.switch.switch_screen('home')),
            ('Tab: Encounter', '^+ f2', lambda *a: self.switch.switch_screen('enc')),
            ('Tab: Info 1', '^+ f3', lambda *a: self.switch.switch_screen('info1')),
            ('Tab: Info 2', '^+ f4', lambda *a: self.switch.switch_screen('info2')),
        ]:
            self.app_hotkeys.register(*params)
        if not DEV_BUILD:
            Assets.play_sfx('ui', 'welcome', volume='ui')

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
        raw_resolution = Settings.get_setting('full_resolution' if full else 'window_resolution', 'General').split(', ')
        return tuple(int(_) for _ in raw_resolution)

    @property
    def fps_color(self):
        return (1, 0, 0, (FPS-self.fps.rate)/45)

    def mainloop_hook(self, dt):
        self.fps.tick()
        s = widgets.kvWindow.size
        self.title = f'{TITLE} | {round(self.fps.rate)} FPS, {s[0]}×{s[1]}'

        encounter_api = self.game.encounter_api
        if self.encounter is None and encounter_api is not None:
            self.enc_frame.clear_widgets()
            self.encounter = self.enc_frame.add(Encounter(encounter_api))
            self.switch.switch_screen('enc')
            self.home_hotkeys.deactivate()
            self.enc_hotkeys.activate()
            logger.info(f'GUI opened encounter')
        elif self.encounter is not None and encounter_api is None:
            self.enc_hotkeys.clear_all()
            self.enc_frame.remove_widget(self.encounter)
            self.enc_frame.add(ENC_PLACEHOLDER)
            self.encounter = None
            self.switch.switch_screen('home')
            self.home_hotkeys.activate()
            self.enc_hotkeys.deactivate()
            logger.info(f'GUI closed encounter')

        self.enc_hotkeys.deactivate()
        if self.encounter is None or self.switch.current_screen.name == 'home':
            self.enc_hotkeys.deactivate()
            self.home.update()
        elif self.encounter is not None and self.switch.current_screen.name == 'enc':
            self.enc_hotkeys.activate()
            self.encounter.update()


class InfoBox(widgets.BoxLayout):
    def __init__(self, label, widget=None, label_color=None, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        label_frame = self.add(widgets.AnchorLayout(anchor_y='top'))
        label_frame.set_size(y=50)
        label_widget = widgets.Label(text=label, markup=True, color=(0,0,0,1))
        label_widget.make_bg((0.5, 0.5, 0.5, 1))
        label_frame.add(label_widget)
        if widget:
            widget_frame = self.add(widgets.AnchorLayout())
            widget_frame.add(widget)
        else:
            self.add(widgets.Widget())



INFO_PANEL1 = InfoBox(f'Press [b]Ctrl[/b]+[b]Shift[/b]+[b]F2[/b] to return to encounter', widgets.Image(allow_stretch=True, source=Assets.get_sprite('ui', 'scaling-table')))
INFO_PANEL2 = InfoBox(f'Press [b]Ctrl[/b]+[b]Shift[/b]+[b]F2[/b] to return to encounter', widgets.Image(allow_stretch=True, source=Assets.get_sprite('ui', 'scaling-table-full')))
ENC_PLACEHOLDER = InfoBox(f'Press [b]Ctrl[/b]+[b]Shift[/b]+[b]F1[/b] to load an encounter', widgets.Label(text='No encounter in progress.'))
