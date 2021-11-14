from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from data.load import Assets, resource_name
from logic.mechanics.common import *


class HUD(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        main_panel = self.add(widgets.BoxLayout(orientation='vertical'))
        main_panel.set_size(y=250)

        ability_panel = main_panel.add(widgets.AnchorLayout(anchor_y='bottom'))
        self.ability_bar = ability_panel.add(AbilityBar(enc=self.enc))

        self.hp_bar = main_panel.add(StatBar(STAT.HP, (1, 0, 0, 0.4), 'HP', enc=self.enc))
        self.mana_bar = main_panel.add(StatBar(STAT.MANA, (0, 0, 1, 0.4), 'Mana', enc=self.enc))

    def update(self):
        self.ability_bar.update()
        self.hp_bar.update()
        self.mana_bar.update()


class StatBar(widgets.BoxLayout, EncounterViewComponent):
    def __init__(self, stat, color, text, **kwargs):
        super().__init__(**kwargs)
        self.stat = stat
        self.label_text = text
        self.set_size(y=35)
        self.make_bg(color)

        self.label = self.add(widgets.Label()).set_size(x=200)
        self.bar = self.add(widgets.ProgressBar())

    def update(self):
        stat_current, stat_max, stat_delta = self.api.get_stats(0, self.stat, value_name=(VALUE.CURRENT, VALUE.MAX_VALUE, VALUE.DELTA))
        stat_delta *= self.api.s2ticks()
        stat_delta_str = f'(+ {stat_delta:.2f})' if stat_delta > 0 else ''
        self.label.text = f'{self.label_text}: {stat_current:.2f} / {stat_max:.2f}{stat_delta_str}'
        self.bar.value = 100 * stat_current / stat_max


class AbilityBar(widgets.GridLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 4
        self.set_size(hx=0.4, y=150)
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
                self.add(AbilityPanel(self.api.get_ability(aid)))


class AbilityPanelFrame(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.set_size(hx=0.25, hy=0.5)

    def update(self, api):
        pass


class AbilityPanel(AbilityPanelFrame):
    def __init__(self, ability, **kwargs):
        super().__init__(**kwargs)
        self.ability = ability
        self.make_bg()
        self._bg_color.rgba = (*ability.color, 0.4)
        res_name = resource_name(ability.aid.name)
        self.im = self.add(widgets.Image(
            source=Assets.get_sprite('ability', res_name),
            allow_stretch=True,
        )).set_size(hx=0.5)
        self.label = self.add(widgets.Label(text=f'{ability.name}'))
        with self.im.canvas.after:
            self.color = widgets.kvColor(0, 0, 0, 0)
            self.rect = widgets.kvRectangle(pos=(0, 0), size=self.size)

    def update(self, api):
        cd = api.get_cooldown(0, self.ability.aid)
        text = f'{self.ability.name}'
        if cd > 0:
            color = (0, 0, 0, 0.7)
            text += f' ({api.ticks2s(cd):.1f})'
        else:
            color = (0, 0, 0, 0)
        # self.im.pos =
        self.color.rgba = color
        self.label.text = text
        self.rect.pos = self.pos
        self.rect.size = self.size
