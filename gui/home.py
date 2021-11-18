
import numpy as np
from logic.encounter.api import EncounterAPI
from logic.mechanics.common import *
from logic.mechanics.mechanics import Mechanics
import nutil
from nutil import kex
from nutil.vars import modify_color
from nutil.display import make_title
from nutil.kex import widgets
from data.load import Assets, Settings


class HomeGUI(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        self.menu = self.add(Menu(buttons={
            'Start Encounter': lambda: self.next_encounter.start(),
            'Restart': nutil.restart_script,
            'Quit': lambda *a: quit(),
        }))
        self.next_encounter = self.add(NextEncounter())


class Menu(widgets.BoxLayout):
    def __init__(self, buttons, **kwargs):
        super().__init__(**kwargs)
        self.set_size(y=50)

        for t, m in buttons.items():
            self.add(widgets.Button(
                text=t, on_release=lambda *a, x=m: x())).set_size(x=150)


class NextEncounter(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.draft = self.add(Draft())
        self.app.hotkeys.register_dict({
            'New encounter': ('enter', self.start),
            'New encounter (2nd)': ('numpadenter', self.start),
        })

    def start(self):
        self.app.start_encounter(aids=self.selected_abilities)

    @property
    def selected_abilities(self):
        return self.draft.selected_abilities


class Draft(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_abilities = self.default_loadout()

        self.ability_viewer = self.add(AbilityViewer()).set_size(x=400)
        draft_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        self.choice_frame = draft_frame.add(DraftAllAbilities(self.click_ability, True))
        self.loadout_frame = draft_frame.add(DraftedAbilities(self.click_ability, False))

        self.choice_frame.set_ability_buttons(self.selected_abilities)
        self.loadout_frame.set_ability_buttons(self.selected_abilities)

    def click_ability(self, aid, draft=None):
        if draft is True:
            if aid not in self.selected_abilities:
                for si, aid_ in enumerate(self.selected_abilities):
                    if aid_ is None:
                        self.selected_abilities[si] = aid
                        break
                else:
                    print('Tried drafting ability with full loadout')
        elif draft is False:
            if aid in self.selected_abilities:
                si = self.selected_abilities.index(aid)
                self.selected_abilities[si] = None
            else:
                raise ValueError(f'Trying to undraft {aid} not yet drafted: {self.selected_abilities}')
        else:
            self.view_ability(aid)
        self.choice_frame.set_ability_buttons(self.selected_abilities)
        self.loadout_frame.set_ability_buttons(self.selected_abilities)

    def view_ability(self, aid):
        self.ability_viewer.set_ability(aid)

    def default_loadout(self):
        return list(ABILITY)[:8]


class DraftAllAbilities(widgets.StackLayout):
    def __init__(self, callback, mode, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.mode = mode

    def set_ability_buttons(self, drafted):
        self.clear_widgets()
        for aid in ABILITY:
            if aid in drafted:
                self.add(AbilityButtonFrame())
            else:
                self.add(AbilityButton(Mechanics.abilities[aid], self.callback, self.mode))


class DraftedAbilities(widgets.GridLayout):
    def __init__(self, callback, mode, **kwargs):
        super().__init__(**kwargs)
        self.cols = 4
        self.set_size(y=200)
        self.callback = callback
        self.mode = mode

    def set_ability_buttons(self, drafted):
        self.clear_widgets()
        for aid in drafted:
            if aid is None:
                self.add(AbilityButtonFrame())
            else:
                self.add(AbilityButton(Mechanics.abilities[aid], self.callback, self.mode))


class AbilityViewer(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(anchor_x='left', anchor_y='top', **kwargs)
        self.label = self.add(widgets.Label(halign='left', valign='top'))
        self.label.text_size = self.label.size

    def set_ability(self, aid):
        if aid is None:
            return
        ability = Mechanics.abilities[aid]
        Assets.play_sfx('ability', ability.name,
                        volume=Settings.get_volume('ui'),
                        allow_exception=False)
        self.make_bg(modify_color(ability.color, 0.3))
        self.label.text = f'{make_title(ability.name, length=30, end_line=False)}\n{ability.description}'
        self.label.text_size = self.label.size


class AbilityButtonFrame(widgets.BoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_size(200, 100)


class AbilityButton(widgets.kvButtonBehavior, AbilityButtonFrame):
    def __init__(self, ability, callback, mode, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.callback = callback
        self.mode = mode
        self.ability = ability
        self.im = self.add(widgets.Image(source=Assets.get_sprite('ability', ability.sprite)))
        self.label = self.add(widgets.Label(text=self.ability.name[:30]))
        color = (*self.ability.color[:3], 0.4)
        self.make_bg(color)

    def on_touch_down(self, m):
        if not self.collide_point(*m.pos):
            return
        if m.button == 'left':
            self.callback(self.ability.aid)
        if m.button == 'right':
            self.callback(self.ability.aid, draft=self.mode)
        return True
