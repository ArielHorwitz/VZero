import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
import nutil
from nutil import kex
from nutil.display import make_title
from nutil.kex import widgets
from data import TITLE, DEV_BUILD
from data.assets import Assets
from data.settings import Settings
from gui.common import SpriteLabel, SpriteTitleLabel, CenteredSpriteBox, Stack
from engine.common import *


class HomeGUI(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui', 'home')

        main_anchor = self.add(widgets.AnchorLayout()).set_size(1024, 768)

        main_frame = main_anchor.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.make_bg((0,0,0,0.5))
        self.title_label = main_frame.add(widgets.Label(halign='center', valign='middle', markup=True)).set_size(y=100)
        self.menu = main_frame.add(Menu())
        self.menu.set_size(y=30)
        self.draft = main_frame.add(Draft())

        corner_anchor = main_anchor.add(widgets.AnchorLayout(anchor_x='right', anchor_y='top'))
        corner_buttons = corner_anchor.add(widgets.BoxLayout())
        if DEV_BUILD:
            corner_buttons.add(widgets.Button(text='Restart', on_release=lambda *a: nutil.restart_script())).set_size(x=100, y=30)
        corner_buttons.add(widgets.Button(text='Quit', on_release=lambda *a: self.app.stop())).set_size(x=100, y=30)
        corner_buttons.set_size(x=100*len(corner_buttons.children), y=30)
        self.make_hotkeys()

    def update(self):
        self.app.game.update()
        enc_str = f'\nPress [b]Ctrl[/b]+[b]Shift[/b]+[b]F2[/b] to return to encounter\n' if self.app.encounter else ''
        self.title_label.text = f'{TITLE}\n{enc_str}\n{self.app.game.title_text}'
        self.draft.update()

    def make_hotkeys(self):
        for i in range(10):
            self.app.home_hotkeys.register(
                f'Home number select {i}', str(i),
                lambda _, x=i: self.app.game.number_select(x)
            )
        for action, key, callback in [
            ('Home enter', 'enter', lambda _: self.app.game.save()),
            ('Home enter', 'numpadenter', lambda _: self.app.game.save()),
        ]:
            self.app.home_hotkeys.register(action, key, callback)


class Menu(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = self.add(widgets.BoxLayout())
        self.box.add(widgets.Label(text='[b][u]Play difficulty:[/u][/b]', markup=True))
        for t, m in {
            **{mode: lambda _=i: self.app.game.new_encounter(difficulty_level=_) for i, mode in enumerate(self.app.game.difficulty_levels)},
        }.items():
            b = widgets.Button(
                # background_down=Assets.get_sprite('ui', 'mask-1x8'),
                background_normal=Assets.get_sprite('ui', 'mask-8x1'),
                background_color=(.4,.4,.4),
                text=t, on_release=lambda *a, x=m: x())
            self.box.add(b)
        self.box.set_size(x=150*len(self.box.children), y=30)


class Draft(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        self.make_bg((.1,.1,.1,1))
        top_frame = self.add(widgets.BoxLayout())
        self.details = top_frame.add(SpriteTitleLabel()).set_size(x=300)
        self.draft = top_frame.add(Stack(
            wtype=lambda *a, **k: CenteredSpriteBox(*a, size_hint=(.9, .9), valign='bottom', **k),
            callback=self.app.game.draft_click,
            x=50, y=50))
        self.draft.make_bg((.1,.1,.1,1))

        bottom_frame = self.add(widgets.BoxLayout()).set_size(y=100)
        self.label = bottom_frame.add(widgets.Label(valign='top'))
        self.label.make_bg((.1,.15,.1,1))
        self.label._bg.source = Assets.get_sprite('ui', 'mask-4x1')
        self.loadout = bottom_frame.add(Stack(
            wtype=SpriteLabel, x=175, y=50,
            callback=self.app.game.loadout_click,
            drag_drop_callback=self.app.game.loadout_drag_drop,
            ))
        self.loadout.set_size(x=700)
        self.loadout.make_bg((.1,.1,.1,1))

    def update(self):
        self.draft.update(self.app.game.draft_boxes())
        self.loadout.update(self.app.game.loadout_boxes())
        self.details.update(self.app.game.draft_details())
        self.label.text = self.app.game.draft_label()
        self.label.text_size = self.label.size
