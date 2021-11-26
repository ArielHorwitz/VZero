from collections import namedtuple
from nutil.display import make_title
from nutil.vars import modify_color
from nutil.kex import widgets
from data.assets import Assets
from gui.encounter import EncounterViewComponent


class AbilityInfo(widgets.BoxLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.grid = self.add(widgets.GridLayout(cols=4))
        self.boxes = []
        for i in range(len(self.api.units[0].abilities)):
            ability = self.api.abilities[i]
            box = self.grid.add(widgets.BoxLayout(orientation='vertical'))
            header = box.add(widgets.BoxLayout())
            header.set_size(y=50)
            im = header.add(widgets.Image(
                source=Assets.get_sprite('ability', ability.sprite),
                allow_stretch=True))
            im.set_size(80, 50)
            name = header.add(widgets.Label(text=ability.name, valign='middle'))
            label = box.add(widgets.Label(halign='left', valign='top'))
            self.boxes.append(AbilityBox(box, im, name, label))
        self.update()

    def update(self):
        for i, aid in enumerate(self.api.units[0].abilities):
            ability = self.api.abilities[aid]
            box = self.boxes[i]
            box.box.make_bg(modify_color(ability.color, 0.3))
            box.name_tag.text_size = box.name_tag.size
            box.label.text = f'\n{ability.description(self.api, 0)}'
            box.label.text_size = box.label.size


AbilityBox = namedtuple('AbilityBox', ['box', 'image', 'name_tag', 'label'])
