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
from logic.encounter.encounter import Encounter as LogicAPI



class App(widgets.App):
    def __init__(self, **kwargs):
        logger.info(f'Initializing GUI @ {FPS} fps.')
        super().__init__(make_bg=False, make_menu=False, **kwargs)
        self.hotkeys.register_dict({
            'Tab: Home': (' f1', lambda: self.switch.switch_screen('home')),
            'Tab: Encounter': (' f2', lambda: self.switch.switch_screen('enc')),
        })
        self.icon = str(Path.cwd()/'icon.png')
        widgets.kvWindow.maximize()

        self.switch = self.add(widgets.ScreenSwitch())
        self.home = HomeGUI()
        self.encounter = None
        self.enc_frame = widgets.BoxLayout()
        self.switch.add_screen('home', self.home)
        self.switch.add_screen('enc', self.enc_frame)

        # Start mainloop
        self.fps = RateCounter(sample_size=FPS)
        self.hook_mainloop(FPS)

    def start_encounter(self, aids):
        if self.encounter is not None:
            return
        api = LogicAPI.new_encounter(player_abilities=aids)
        self.encounter = self.enc_frame.add(Encounter(api))
        self.switch.switch_screen('enc')

    def end_encounter(self):
        if self.encounter is None:
            return
        self.switch.switch_screen('home')
        self.enc_frame.remove_widget(self.encounter)
        self.encounter = None

    def mainloop_hook(self, dt):
        self.fps.tick()
        self.title = f'{TITLE} | FPS: {round(self.fps.rate)} ({self.fps.mean_elapsed_ms:.1f} ms)'
        if self.encounter is not None:
            self.encounter.update()
