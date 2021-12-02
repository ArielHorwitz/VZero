
import numpy as np
import nutil
from nutil import kex
from nutil.display import make_title
from nutil.kex import widgets
from data.assets import Assets
from data.settings import Settings
from gui.common import SpriteLabel
from engine.common import *


class HomeGUI(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        self.menu = self.add(Menu())
        self.draft = self.add(Draft())

        self.app.hotkeys.register_dict({
            'New encounter': (
                f'{Settings.get_setting("start_encounter", "Hotkeys")}',
                lambda: self.app.game.new_encounter()),
        })

    def update(self):
        self.draft.update()


class Menu(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_size(y=50)

        for t, m in {
            'Start Encounter': lambda: self.app.game.new_encounter(),
            'Restart': nutil.restart_script,
            'Quit': lambda *a: quit(),
        }.items():
            self.add(widgets.Button(
                text=t, on_release=lambda *a, x=m: x())).set_size(x=150)


class Draft(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.viewer = self.add(widgets.BoxLayout(orientation='vertical'))
        self.viewer.make_bg((0, 0.2, 0.5, 0.5))
        self.slbox = self.viewer.add(SpriteLabel())
        self.slbox.set_size(y=200)
        self.label = self.viewer.add(widgets.Label(valign='top'))
        self.label.make_bg((0, 0, 0, 0.2))

        right_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        draft_frame = right_frame.add(widgets.StackLayout())
        loadout_frame = right_frame.add(widgets.GridLayout(cols=4))
        loadout_frame.set_size(hy=0.2)

        sample_draft = self.app.game.draft_boxes()
        self.draft_boxes = []
        for i in range(len(sample_draft)):
            btn = DraftButton(i, self.draft_click)
            draft_frame.add(btn)
            btn.set_size(x=150, y=50)
            self.draft_boxes.append(btn)
        self.loadout_boxes = [loadout_frame.add(DraftButton(_, self.loadout_click)) for _ in range(8)]

        self.bind(size=self.reposition)

    def reposition(self, *a):
        self.viewer.set_size(x=300 if self.size[0] <= 1024 else 400)

    def update(self):
        for i, sl in enumerate(self.app.game.draft_boxes()):
            self.draft_boxes[i].update(sl)
        for i, sl in enumerate(self.app.game.loadout_boxes()):
            self.loadout_boxes[i].update(sl)
        self.slbox.update(self.app.game.draft_info_box())
        self.label.text = self.app.game.draft_info_label()
        self.label.text_size = self.label.size

    def draft_click(self, index, m):
        self.app.game.draft_click(index, m.button)

    def loadout_click(self, index, m):
        self.app.game.loadout_click(index, m.button)


class DraftButton(SpriteLabel):
    def __init__(self, index, callback, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.callback = callback
        self.bind(on_touch_down=self.click)

    def click(self, w, m):
        if self.collide_point(*m.pos):
            self.callback(self.index, m)
