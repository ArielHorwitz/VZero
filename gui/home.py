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
from gui.api import ControlEvent
from gui.common import SpriteLabel, SpriteTitleLabel, CenteredSpriteBox, Stack, Tooltip
from logic.common import *


HOME_SIZE = 1024, 768
DETAILS_WIDTH = 300
CONTROL_BUTTON_WORLD = 'Select Encounter'
CONTROL_BUTTON_ENCOUNTER = 'Return to World'


class HomeGUI(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui.home')

        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.set_size(*HOME_SIZE)
        main_frame.make_bg((0,0,0,0.5))
        self.app_control = main_frame.add(self.app.generate_app_control_buttons())
        self.app.interface.register('set_title_text', self.set_title_text)

        self.screen_switch = main_frame.add(widgets.ScreenSwitch(transition=widgets.kvFadeTransition(duration=0.25)))
        self.draft = Draft()
        self.world = World()
        self.screen_switch.add_screen('world', view=self.world)
        self.screen_switch.add_screen('draft', view=self.draft)
        self.app.interface.register('set_view', self.switch_screen)
        self.tooltip = self.add(Tooltip(bounding_widget=self))
        self.app.interface.register('activate_tooltip', lambda x: self.tooltip.activate(self.app.mouse_pos, x))

        self.make_hotkeys()

    def make_hotkeys(self):
        self.app.home_hotkeys.register('Home enter', 'enter', self.save_loadout)
        self.app.home_hotkeys.register_keys('Home enter', ['numpadenter'])
        for i in range(10):
            self.app.home_hotkeys.register(
                f'Home select preset {i}', str(i),
                lambda _, x=i: self.select_preset(x)
            )

    def update(self):
        self.app.game.update()

    def switch_screen(self, sname):
        logger.info(f'Home switching to screen: {sname}')
        self.screen_switch.switch_screen(sname)

    def set_title_text(self, text):
        self.app_control.title.text = text

    def save_loadout(self, *a):
        self.app.interface.append(ControlEvent('save_loadout', 0, f'Save loadout (index always 0)'))

    def select_preset(self, index):
        self.app.interface.append(ControlEvent('select_preset', index, f'Select preset'))


class World(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        details_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        details_frame.set_size(x=DETAILS_WIDTH)
        # controls
        self.control_buttons = details_frame.add(Stack(wtype=SpriteLabel, callback=self.control_click))
        self.control_buttons.set_size(y=80).make_bg((0.1,0.25,0.1,1))
        self.app.interface.register('set_world_control_buttons', self.control_buttons.update)
        self.bind(size=self.resize)
        # details
        self.details = details_frame.add(SpriteTitleLabel())
        self.app.interface.register('set_world_details', self.details.update)

        # encounters
        self.encounter_stack = self.add(Stack(
            wtype=lambda *a, **k: CenteredSpriteBox(*a, margin=(.5, .5), valign='bottom', **k),
            callback=self.world_click, x=75, y=75))
        self.app.interface.register('set_world_stack', self.encounter_stack.update)

    def resize(self, *a):
        self.control_buttons.set_boxsize((self.control_buttons.size[0], 40))

    def control_click(self, index, button):
        self.app.interface.append(ControlEvent('world_control_button', index, 'World control button'))

    def world_click(self, index, button):
        if button == 'left':
            self.app.interface.append(ControlEvent('world_stack_inspect', index, 'World stack left click'))
        elif button == 'right':
            self.app.interface.append(ControlEvent('world_stack_activate', index, 'World stack right click'))


class Draft(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # details
        self.draft_details = self.add(DraftDetails())
        self.draft_details.set_size(x=DETAILS_WIDTH)

        # draft
        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        self.draft = main_frame.add(Stack(
            wtype=CenteredSpriteBox,
            callback=self.draft_click,
            x=50, y=50))
        self.app.interface.register('set_draft_stack', self.draft.update)
        # loadout
        self.loadout = main_frame.add(Stack(
            wtype=SpriteLabel, x=175, y=50,
            callback=self.loadout_click,
            drag_drop_callback=self.loadout_drag_drop,
            ))
        self.app.interface.register('set_loadout_stack', self.loadout.update)
        self.loadout.set_size(y=100)

        self.bind(pos=self.reposition, size=self.reposition)

    def reposition(self, *a):
        self.loadout.set_boxsize(((self.size[0]-DETAILS_WIDTH)/4, 50))

    def draft_click(self, index, button):
        if button == 'left':
            self.app.interface.append(ControlEvent(f'draft_inspect', index, ''))
        elif button == 'right':
            self.app.interface.append(ControlEvent(f'draft_activate', index, ''))

    def loadout_click(self, index, button):
        if button == 'left':
            self.app.interface.append(ControlEvent(f'loadout_inspect', index, ''))
        elif button == 'right':
            self.app.interface.append(ControlEvent(f'loadout_activate', index, ''))

    def loadout_drag_drop(self, origin, target, button):
        if button == 'middle':
            self.app.interface.append(ControlEvent(f'loadout_drag_drop', (origin, target), 'Index is tuple of (origin_index, target_index)'))


class DraftDetails(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.control_buttons = self.add(Stack(wtype=SpriteLabel, callback=self.control_click))
        self.control_buttons.set_size(y=80).make_bg((0.1,0.25,0.1,1))
        self.app.interface.register('set_draft_control_buttons', self.control_buttons.update)

        self.details = self.add(SpriteTitleLabel())
        self.app.interface.register('set_draft_details', self.details.update)

        self.bind(size=self.resize)

    def resize(self, *a):
        self.control_buttons.set_boxsize((self.control_buttons.size[0], 40))

    def control_click(self, index, button):
        if button == 'left':
            self.app.interface.append(ControlEvent('draft_control_button', index, ''))
