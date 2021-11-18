from nutil.display import njoin, make_title
from nutil.vars import modify_color
from nutil.kex import widgets
from gui.encounter import EncounterViewComponent


class AbilityInfo(widgets.BoxLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.grid = self.add(widgets.GridLayout(cols=4))
        self.labels = []
        for i in range(len(self.api.units[0].abilities)):
            label = self.grid.add(widgets.Label(halign='left', valign='top'))
            self.labels.append(label)

        self.refresh()

    def refresh(self):
        text = []
        for i, aid in enumerate(self.api.units[0].abilities):
            label = self.labels[i]
            ability = self.api.abilities[aid]
            label.text = self.get_description(ability)
            label.text_size = label.size
            label.make_bg(modify_color(ability.color, 0.3))

    def get_description(self, ability):
        return f'{make_title(ability.name, length=30)}{ability.description}'
