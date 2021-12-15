import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from pathlib import Path
import nutil
from nutil.kex import widgets
from nutil.time import RateCounter, pingpong
from data import TITLE, FPS
from data.settings import Settings
from gui.home import HomeGUI
from gui.encounter.encounter import Encounter
from engine import get_api



class App(widgets.App):
    def __init__(self, **kwargs):
        logger.info(f'Initializing GUI @ {FPS} fps.')
        super().__init__(make_bg=False, make_menu=False, **kwargs)
        self.hotkeys.register_dict({
            'Borderless': ('f11', lambda *a: self.toggle_borderless()),
            'Fullscreen': ('! f11', lambda *a: self.toggle_fullscreen()),
            'Tab: Home': ('^+ home', lambda: self.switch.switch_screen('home')),
            'Tab: Encounter': ('^+ end', lambda: self.switch.switch_screen('enc')),
        })
        self.icon = str(Path.cwd()/'icon.png')

        self.set_window_size(self.configured_resolution(full=False))
        default_window_state = Settings.get_setting('default_window')
        if default_window_state == 'fullscreen':
            self.toggle_fullscreen(True)
        elif default_window_state == 'borderless':
            self.toggle_borderless(True)
        else:
            self.toggle_borderless(False)

        self.game = get_api()

        self.switch = self.add(widgets.ScreenSwitch())
        self.home = HomeGUI()
        self.encounter = None
        self.enc_frame = widgets.BoxLayout()
        self.switch.add_screen('home', self.home)
        self.switch.add_screen('enc', self.enc_frame)

        # Start mainloop
        self.fps = RateCounter(sample_size=FPS)
        self.hook_mainloop(FPS)

    def configured_resolution(self, full=True):
        raw_resolution = Settings.get_setting('full_resolution' if full else 'window_resolution', 'General').split(', ')
        return tuple(int(_) for _ in raw_resolution)

    def toggle_borderless(self, set_as=None):
        if widgets.kvWindow.fullscreen:
            self.toggle_fullscreen(set_as=False)
            return
        set_as = not widgets.kvWindow.borderless if set_as is None else set_as
        logger.debug(f'Setting borderless: {set_as}')
        if set_as is True:
            widgets.kvWindow.borderless = True
            widgets.Clock.schedule_once(lambda *a: widgets.kvWindow.maximize(), 0)
        else:
            widgets.kvWindow.borderless = False
            widgets.Clock.schedule_once(lambda *a: self._restore(), 0)

    def toggle_fullscreen(self, set_as=None):
        set_as = not widgets.kvWindow.fullscreen if set_as is None else set_as
        logger.debug(f'Setting fullscreen: {set_as}')
        if set_as is True:
            self.set_window_size(self.configured_resolution(full=True))
            widgets.Clock.schedule_once(lambda *a: self._toggle_fullscreen(), 0)
        else:
            widgets.kvWindow.fullscreen = False
            widgets.Clock.schedule_once(lambda *a: self.toggle_borderless(set_as=False), 0)

    def _toggle_fullscreen(self, *a):
        widgets.kvWindow.fullscreen = not widgets.kvWindow.fullscreen

    def _restore(self):
        widgets.kvWindow.restore()
        widgets.Clock.schedule_once(lambda *a: self.set_window_size(self.configured_resolution(full=False)), 0)

    @property
    def fps_color(self):
        return (1, 0, 0, (60-self.fps.rate)/30)

    def mainloop_hook(self, dt):
        self.fps.tick()
        s = widgets.kvWindow.size
        self.title = f'{TITLE} | {round(self.fps.rate)} FPS, {s[0]}×{s[1]}'

        encounter_api = self.game.encounter_api
        if self.encounter is None and encounter_api is not None:
            self.encounter = self.enc_frame.add(Encounter(encounter_api))
            self.switch.switch_screen('enc')

        if self.encounter is None:
            self.home.update()
        else:
            self.encounter.update()
