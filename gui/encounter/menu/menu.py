import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import nutil
from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from logic.mechanics.common import *
from gui.encounter.menu.ability_info import AbilityInfo
from gui.encounter.menu.mod_menu import ModMenu


class Menu(widgets.ModalView, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(auto_dismiss=False, **kwargs)
        self.attach_to = self.enc
        # self.dismiss()
        self.__showing = False
        self.set_size(hx=0.75, hy=0.9)

        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))

        tabs = main_frame.add(widgets.BoxLayout())
        tabs.set_size(y=40)
        self.screens = main_frame.add(widgets.ScreenSwitch())
        control_frame = main_frame.add(widgets.BoxLayout())
        control_frame.set_size(y=40)

        # Screens / tabs
        self.ability_info = AbilityInfo(enc=self.enc)
        self.screens.add_screen('Abilities', self.ability_info)
        tabs.add(widgets.Button(
            text='Abilities',
            on_release=lambda *a: self.screens.switch_screen('Abilities')
        ))
        self.mod_menu = ModMenu(enc=self.enc)
        mod_menu_title = self.api.mod_api.menu_title
        self.screens.add_screen(mod_menu_title, self.mod_menu)
        tabs.add(widgets.Button(
            text=mod_menu_title,
            on_release=lambda *a: self.screens.switch_screen(mod_menu_title)
        ))

        # Control buttons
        for t, f in {
            # 'Leave encounter': lambda *a: self.app.end_encounter(),
            'Resume': lambda *a: self.enc.toggle_play(),
            'Restart': lambda *a: nutil.restart_script(),
            'Quit': lambda *a: quit(),
        }.items():
            btn = control_frame.add(widgets.Button(text=t, on_release=f))

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
        if self.api.auto_tick:
            return
        self.ability_info.update()
        self.mod_menu.update()
