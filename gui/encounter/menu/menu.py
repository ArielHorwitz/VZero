import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import nutil
from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from data.settings import Settings
from logic.mechanics.common import *
from gui.encounter.menu.ability_info import AbilityInfo
from gui.encounter.menu.mod_menu import ModMenu


class Menu(widgets.ModalView, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(auto_dismiss=False, **kwargs)
        self.attach_to = self.enc
        # self.dismiss()
        self.__showing = False
        self.set_size(hx=0.65, hy=0.9)

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

        self.app.hotkeys.register_dict({
            'Menu 1': (
                f'{Settings.get_setting("open_menu1", "Hotkeys")}',
                lambda: self.toggle_view('Abilities')
            ),
            'Menu 2': (
                f'{Settings.get_setting("open_menu2", "Hotkeys")}',
                lambda: self.toggle_view(mod_menu_title)
            ),
        })

        # Control buttons
        for t, f in {
            # 'Leave encounter': lambda *a: self.app.end_encounter(),
            'Resume': lambda *a: self.enc.toggle_play(),
            'Restart': lambda *a: nutil.restart_script(),
            'Quit': lambda *a: quit(),
        }.items():
            btn = control_frame.add(widgets.Button(text=t, on_release=f))

        self.bind(on_touch_down=self.click)

    def click(self, w, m):
        if not self.collide_point(*m.pos):
            self.set_view(False)

    @property
    def showing(self):
        return self.__showing

    def toggle_view(self, view):
        if self.__showing and self.screens.current_screen.name == view:
            self.set_view(False)
        else:
            self.set_view(True, view)

    def set_view(self, show=None, view=None):
        if show is None:
            show = not self.__showing
        self.__showing = show
        if self.__showing:
            self.open()
        else:
            self.dismiss()
            if not self.api.auto_tick:
                self.enc.toggle_play(set_to=True)
        if view is not None:
            self.screens.switch_screen(view)

    def update(self):
        if not self.__showing:
            return
        self.ability_info.update()
        self.mod_menu.update()
