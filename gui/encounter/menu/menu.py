import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import nutil
from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from logic.mechanics.common import *
from gui.encounter.menu.ability_info import AbilityInfo


class Menu(widgets.ModalView, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(auto_dismiss=False, **kwargs)
        self.attach_to = self.enc
        # self.dismiss()
        self.__showing = False
        self.set_size(hx=0.75, hy=0.9)

        self.screen_switch = self.add(widgets.ScreenSwitch())
        self.ability_info = AbilityInfo(enc=self.enc)
        self.screen_switch.add_screen('ability-info', self.ability_info)

        # Control buttons
        control_frame = self.add(widgets.BoxLayout())
        for t, f in {
            # 'Leave encounter': lambda *a: self.app.end_encounter(),
            'Resume': lambda *a: self.enc.toggle_play(),
            'Restart': lambda *a: nutil.restart_script(),
            'Quit': lambda *a: quit(),
        }.items():
            btn = control_frame.add(widgets.Button(text=t, on_release=f))
            btn.set_size(y=40)

    @property
    def showing(self):
        return self.__showing

    def set_view(self, show=None):
        if show is None:
            show = not self.__showing
        logger.debug(f'Toggle menu: {self.__showing}')
        self.__showing = show
        if self.__showing:
            self.open()
        else:
            self.dismiss()

    def update(self):
        if self.showing:
            self.ability_info.refresh()
