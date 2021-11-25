import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from data.assets import Assets
from data.settings import Settings
from nutil.kex import widgets, random_color, modify_color
from gui.encounter import EncounterViewComponent


class ModMenu(widgets.BoxLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.grid = self.add(widgets.GridLayout(cols=6))
        self.labels = []
        for i in range(len(self.api.mod_api.menu_texts)):
            label = self.grid.add(widgets.Label(halign='left', valign='top'))
            self.labels.append(label)
            label.bind(on_touch_down=lambda w, m, x=i: self.click(m, x))
        self.update()

    def click(self, m, index):
        if self.labels[index].collide_point(*m.pos):
            right_click = m.button == 'right'
            sfx = self.api.mod_api.menu_click(index, right_click)
            if sfx is not None:
                category, sfx_name = sfx
                Assets.play_sfx(
                    category, sfx_name,
                    volume=Settings.get_volume('sfx'),
                    allow_exception=False)
            return True

    def update(self):
        for i, text in enumerate(self.api.mod_api.menu_texts):
            label = self.labels[i]
            label.text = text
            label.text_size = label.size
            color = self.api.mod_api.menu_colors[i]
            label.make_bg(color)
