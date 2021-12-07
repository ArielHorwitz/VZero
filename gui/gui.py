import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from pathlib import Path
import nutil
from nutil.kex import widgets
from nutil.time import RateCounter, pingpong
from data import TITLE, FPS
from gui.home import HomeGUI
from gui.encounter.encounter import Encounter
from engine import get_api



class App(widgets.App):
    def __init__(self, **kwargs):
        logger.info(f'Initializing GUI @ {FPS} fps.')
        super().__init__(make_bg=False, make_menu=False, **kwargs)
        self.hotkeys.register_dict({
            'Tab: Home': ('f1', lambda: self.switch.switch_screen('home')),
            'Tab: Encounter': ('f2', lambda: self.switch.switch_screen('enc')),
        })
        self.icon = str(Path.cwd()/'icon.png')
        widgets.kvWindow.maximize()
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
