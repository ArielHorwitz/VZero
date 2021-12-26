import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
import nutil
from nutil import kex
from nutil.display import make_title
from nutil.kex import widgets
from data import TITLE
from data.assets import Assets
from data.settings import Settings
from gui.common import SpriteLabel, SpriteTitleLabel, CenteredSpriteBox, Stack
from engine.common import *


class HomeGUI(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui', 'portrait-frame')

        main_anchor = self.add(widgets.AnchorLayout()).set_size(1024, 768)

        main_frame = main_anchor.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.make_bg((0,0,0,0.5))
        self.title_label = main_frame.add(widgets.Label(halign='center', valign='middle')).set_size(y=100)
        self.menu = main_frame.add(Menu())
        self.menu.set_size(y=30)
        self.draft = main_frame.add(Draft())

        corner_anchor = main_anchor.add(widgets.AnchorLayout(anchor_x='right', anchor_y='top'))
        corner_buttons = corner_anchor.add(widgets.BoxLayout()).set_size(x=200, y=30)
        corner_buttons.add(widgets.Button(text='Restart', on_release=lambda *a: nutil.restart_script())).set_size(x=100, y=30)
        corner_buttons.add(widgets.Button(text='Quit', on_release=lambda *a: quit())).set_size(x=100, y=30)

        for params in [
            ('New encounter', f'{Settings.get_setting("start_encounter", "Hotkeys")}', lambda *a: self.app.game.new_encounter()),
        ]:
            self.app.home_hotkeys.register(*params)

    def update(self):
        self.title_label.text = f'{TITLE}\n\n{self.app.game.title_text}'
        self.draft.update()


class Menu(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for t, m in {
            'Play': lambda: self.app.game.new_encounter(),
            **{b: lambda x=i: self.app.game.button_click(x) for i, b in enumerate(self.app.game.button_names)},
        }.items():
            b = widgets.Button(
                text=t, on_release=lambda *a, x=m: x())
            self.add(b).set_size(x=100, y=30)


class Draft(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        top_frame = self.add(widgets.BoxLayout())
        self.details = top_frame.add(SpriteTitleLabel()).set_size(x=300)
        self.draft = top_frame.add(Stack(
            wtype=lambda *a: CenteredSpriteBox(*a, size_hint=(.9, .9)),
            callback=self.app.game.draft_click,
            x=50, y=50))
        self.draft.make_bg((.1,.1,.1,1))

        bottom_frame = self.add(widgets.BoxLayout()).set_size(y=100)
        self.label = bottom_frame.add(widgets.Label(valign='top'))
        self.loadout = bottom_frame.add(Stack(
            wtype=SpriteLabel,
            x=150, y=50,
            callback=self.app.game.loadout_click))
        self.loadout.set_size(x=600)

    def update(self):
        self.draft.update(self.app.game.draft_boxes())
        self.loadout.update(self.app.game.loadout_boxes())
        self.details.update(self.app.game.draft_details())
        self.label.text = self.app.game.draft_label()
        self.label.text_size = self.label.size


class DraftButton(SpriteLabel):
    def __init__(self, index, callback, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.callback = callback
        self.bind(on_touch_down=self.click)

    def click(self, w, m):
        if self.collide_point(*m.pos):
            self.callback(self.index, m)


#
