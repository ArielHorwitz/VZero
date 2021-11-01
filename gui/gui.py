
import os
from nutil.kex import widgets
from nutil.time import RateCounter

from gui.encounter.encounter import EncounterGUI


VERSION = 0.001
NAME = f'Roguesque'
TITLE = f'{NAME} v{VERSION}'
SPRITE_DIR = os.getcwd() + '/gui/sprites/'
FPS = 60


class App(widgets.App):
    def __init__(self, **kwargs):
        super().__init__(make_bg=False, make_menu=False, **kwargs)
        self.icon = SPRITE_DIR + 'goal.png'
        widgets.kvWindow.maximize()
        self.encounter = self.add(EncounterGUI())

        # Start mainloop
        self.fps = RateCounter(sample_size=FPS)
        self.hook_mainloop(FPS)

    def mainloop_hook(self, dt):
        self.fps.tick()
        self.title = f'{TITLE} | FPS: {round(self.fps.rate)} ({self.fps.mean_elapsed_ms:.1f} ms)'
        self.encounter.frame_update()
