import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from nutil.kex import widgets
from nutil.vars import modify_color
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from logic.mechanics.common import *


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__updating = False

        self.main_panel = self.add(widgets.BoxLayout(orientation='vertical'))
        self.main_panel.set_size(y=250)

        ability_panel = self.main_panel.add(widgets.AnchorLayout(anchor_y='bottom'))
        self.ability_bar = ability_panel.add(AbilityBar(enc=self.enc))

    def update(self):
        if not self.enc.map_mode:
            self.main_panel.pos = 0, 0
            self._update()
            self.__updating = True
        elif self.__updating:
            self.main_panel.pos = self.enc.OUT_OF_DRAW_ZONE
            self._update()
            self.__updating = False

    def _update(self):
        self.ability_bar.update()


class AbilityBar(widgets.GridLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 4
        self.set_size(x=800, y=150)
        self.make_bg((0.5, 0, 0.8, 0.1))
        self.reload_abilities()

    def update(self):
        for panel in self.children:
            panel.update(self.api)

    def reload_abilities(self):
        self.clear_widgets()
        for i, aid in enumerate(self.api.units[0].ability_order):
            if aid is None:
                self.add(AbilityPanelFrame())
            else:
                self.add(AbilityPanel(self.api.get_ability(aid), enc=self.enc))


class AbilityPanelFrame(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.set_size(hx=0.25, hy=0.5)

    def update(self, api):
        pass


class AbilityPanel(AbilityPanelFrame, EncounterViewComponent):
    def __init__(self, ability, **kwargs):
        super().__init__(**kwargs)
        self.ability = ability
        self.im = self.add(widgets.Image(
            source=Assets.get_sprite('ability', ability.aid.name),
            allow_stretch=True,
        )).set_size(hy=0.5)
        self.add(widgets.Label(text=f'{ability.name}')).set_size(hy=0.25)
        self.state_label = self.add(widgets.Label()).set_size(hy=0.25)
        with self.im.canvas.before:
            self.color = widgets.kvColor(0, 0, 0, 0)
            self.rect = widgets.kvRectangle(pos=(0, 0), size=self.size)

    def update(self, api):
        cd = api.get_cooldown(0, self.ability.aid)
        cast_state = self.ability.gui_state(api, 0)
        text = f'{cast_state.string}'
        self.color.rgba = modify_color(cast_state.color, a=0.4)
        self.state_label.text = text
        self.rect.pos = self.pos if not self.enc.map_mode else self.enc.OUT_OF_DRAW_ZONE
        self.rect.size = self.size
