import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import numpy as np
import nutil
from nutil import kex
from nutil.display import make_title
from nutil.kex import widgets
from data import BASE_RESOLUTION
from data.settings import PROFILE
from data.assets import Assets
from gui.api import ControlEvent, MOUSE_EVENTS
from gui.common import SpriteLabel, SpriteTitleLabel, CenteredSpriteBox, Stack, Tooltip
from logic.common import *


DETAILS_WIDTH = 300
CONTROL_BUTTON_WORLD = 'Select Encounter'
CONTROL_BUTTON_ENCOUNTER = 'Return to World'


class HomeGUI(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui.home')

        self.main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        self.main_frame.make_bg((0,0,0,0.5))
        self.app_control = self.main_frame.add(self.app.generate_app_control_buttons())
        self.app.interface.register('set_title_text', self.set_title_text)

        self.screen_switch = self.main_frame.add(widgets.ScreenSwitch(transition=widgets.kvFadeTransition(duration=0.25)))
        self.draft = Draft()
        self.world = World()
        self.screen_switch.add_screen('world', view=self.world)
        self.screen_switch.add_screen('draft', view=self.draft)
        self.app.interface.register('set_view', self.switch_screen)
        self.tooltip = self.add(Tooltip(bounding_widget=self, consume_colliding_touch=False))
        self.app.interface.register('activate_tooltip', lambda x: self.tooltip.activate(self.app.mouse_pos, x))
        self.app.settings_notifier.subscribe('ui.allow_stretch', self.setting_allow_stretch)
        self.setting_allow_stretch()

    def setting_allow_stretch(self):
        if PROFILE.get_setting('ui.allow_stretch'):
            self.main_frame.set_size(hx=1, hy=1)
        else:
            self.main_frame.set_size(*BASE_RESOLUTION)

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
        self.control_buttons = details_frame.add(Stack(
            name='World control',
            wtype=SpriteLabel, callback=self.control_click))
        self.control_buttons.set_size(y=80).make_bg((0.1,0.25,0.1,1))
        self.app.interface.register('set_world_control_buttons', self.control_buttons.update)
        self.bind(size=self.resize)
        # details
        self.details = details_frame.add(SpriteTitleLabel())
        self.app.interface.register('set_world_details', self.details.update)

        # encounters
        self.encounter_stack = self.add(Stack(
            name='World encounters',
            wtype=lambda *a, **k: CenteredSpriteBox(*a, margin=(.5, .5), valign='bottom', **k),
            callback=self.world_click, x=75, y=75))
        self.app.interface.register('set_world_stack', self.encounter_stack.update)

    def resize(self, *a):
        self.control_buttons.set_boxsize((self.control_buttons.size[0], 40))

    def control_click(self, index, button):
        self.app.interface.append(ControlEvent('world_control_button', index, 'World control button'))

    def world_click(self, index, button):
        self.app.interface.append(ControlEvent(f'world_stack_{MOUSE_EVENTS[button]}', index, 'World stack click'))

    def set_auto_hover(self):
        if PROFILE.get_setting('ui.detailed_mode') and PROFILE.get_setting('ui.auto_tooltip'):
            self.encounter_stack.hover_invokes = 'middle'
        else:
            self.encounter_stack.hover_invokes = None


class Draft(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # details
        self.draft_details = self.add(DraftDetails())
        self.draft_details.set_size(x=DETAILS_WIDTH)

        # draft
        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        self.draft = Stack(
            name='Draft abilities',
            wtype=CenteredSpriteBox, x=75, y=75,
            callback=self.draft_click)
        self.draft_frame = main_frame.add(widgets.ScrollViewNew(self.draft))
        self.draft.set_size(hx=1, hy=None)
        self.draft.bind(size=self.resize_draft)
        self.app.interface.register('set_draft_stack', self.draft_update)
        # loadout
        self.loadout = main_frame.add(Stack(
            name='Draft loadout',
            wtype=SpriteLabel, x=175, y=50,
            callback=self.loadout_click,
            drag_drop_callback=self.loadout_drag_drop))
        self.loadout.bind(size=self.resize_loadout)
        self.loadout.set_size(y=100)
        self.app.interface.register('set_loadout_stack', self.loadout.update)

    def draft_update(self, *a, **k):
        self.draft.update(*a, **k)
        self.resize_draft()

    def resize_draft(self, *a):
        self.draft.fix_height(minimum=int(self.draft_frame.height))

    def resize_loadout(self, *a):
        self.loadout.set_boxsize((self.loadout.size[0]/4, 50))
        self.resize_draft()

    def draft_click(self, index, button):
        self.app.interface.append(ControlEvent(f'draft_{MOUSE_EVENTS[button]}', index, 'World stack click'))

    def loadout_click(self, index, button):
        self.app.interface.append(ControlEvent(f'loadout_{MOUSE_EVENTS[button]}', index, 'Loadout click'))

    def loadout_drag_drop(self, origin, target, button):
        mouse_event = MOUSE_EVENTS[button]
        if mouse_event == 'select':
            self.app.interface.append(ControlEvent(f'loadout_drag_drop', (origin, target), 'Index is tuple of (origin_index, target_index)'))

    def set_auto_hover(self):
        set_as = None
        if PROFILE.get_setting('ui.detailed_mode') and PROFILE.get_setting('ui.auto_tooltip'):
            set_as = 'middle'
        self.draft.hover_invokes = set_as
        self.loadout.hover_invokes = set_as


class DraftDetails(widgets.BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.control_buttons = self.add(Stack(
            name='Draft control', wtype=SpriteLabel, callback=self.control_click))
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
