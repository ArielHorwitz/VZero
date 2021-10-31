
from nutil.gui.kex import widgets
from nutil.time import RateCounter

from gui.encounter.encounter import EncounterGUI


FPS = 30

class App(widgets.App):
    def __init__(self, **kwargs):
        super().__init__(make_bg=False, **kwargs)
        widgets.kvWindow.maximize()
        self.encounter = self.add(EncounterGUI())

        # Start mainloop
        self.fps = RateCounter(sample_size=FPS)
        self.hook_mainloop(FPS)

    def mainloop_hook(self, dt):
        self.fps.tick()
        self.title = f'fps: {round(self.fps.rate)} ({self.fps.mean_elapsed_ms:.1f} ms)'
        self.encounter.frame_update()
