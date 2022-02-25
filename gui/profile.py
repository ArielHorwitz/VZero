import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import math

from nutil.vars import minmax
from nutil.kex import widgets
from data import BASE_RESOLUTION, APP_COLOR, resource_name
from data.settings import PROFILE
from data.assets import Assets

from gui.api import SpriteLabel as APISpriteLabel
from gui.common import Stack, SpriteLabel


SCROLL_SENS = 0.2


class ProfileGUI(widgets.AnchorLayout):
    control_buttons = [
        APISpriteLabel(Assets.get_sprite('ui.save'), 'Save', (0,0.5,0,1)),
        APISpriteLabel(Assets.get_sprite('ui.cancel'), 'Cancel', (0.5,0.25,0,1)),
        APISpriteLabel(Assets.get_sprite('ui.reset'), 'Reset to defaults', (0,0,0.5,1)),
    ]
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui.home')

        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.set_size(*BASE_RESOLUTION)
        main_frame.make_bg((0,0,0,0.75))
        self.app_control = main_frame.add(self.app.generate_app_control_buttons())
        self.app_control.title.text = '[b]Profile[/b]'

        self.buttons = []
        bottom_frame = main_frame.add(widgets.BoxLayout())
        self.button_stack = bottom_frame.add(Stack(
            wtype=lambda *a, **k: SpriteLabel(*a, **k),
            callback=self.button_stack_click, x=200, y=50))
        self.button_stack.set_size(x=200)

        self.panel_switch = bottom_frame.add(widgets.ScreenSwitch(transition=widgets.kvFadeTransition(duration=0.1)))
        self.settings_panels = {name: SettingsPanel_(name, data) for name, data in PROFILE.gui_settings.items()}
        self.set_screens([(panel.name, panel) for panel in self.settings_panels.values()])

    def set_screens(self, screens):
        self.buttons = []
        for i, (name, view) in enumerate(screens):
            sprite = Assets.get_sprite(f'ui.settings-{resource_name(name)}')
            name = f'[b]{name}[/b]'
            self.buttons.append(APISpriteLabel(sprite, name, (0,0,0,0)))
            self.panel_switch.add_screen(name, view=view)
        self.button_stack.update([*self.control_buttons, *self.buttons])

    def button_stack_click(self, index, button):
        if button != 'left':
            return
        if index == 0:
            PROFILE.save_changes()
        elif index == 1:
            PROFILE.cancel_changes()
        elif index == 2:
            PROFILE.reset_to_defaults()
        elif index >= 3:
            self.panel_switch.switch_screen(self.buttons[index-3].text)
        else:
            logger.warning(f'button_stack_click received unknown index: {index} (button: {button})')
            return
        Assets.play_sfx('ui.select', volume='ui')


class SettingsPanel_(widgets.BoxLayout):
    def __init__(self, panel_name, data, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.name = panel_name.capitalize()
        sprite = Assets.get_sprite(f'ui.settings-{resource_name(panel_name)}')
        panel_title = SpriteLabel(sprite, self.name, APP_COLOR)
        self.add(panel_title).set_size(y=50)
        self.scrollview = self.add(widgets.ScrollView())
        self.scrollview.do_scroll_x = True
        self.scrollview.do_scroll_y = False
        self.scrollview.bar_width = 15
        self.scrollview.scroll_type = ['bars']
        self.settings_frame = self.scrollview.add(widgets.StackLayout(orientation='tb-lr'))
        self.settings_frame.set_size(x=1000)

        self.widget_size = 100, 100
        self.widget_count = 0
        for setting_name, setting_obj in data.items():
            self.settings_frame.add(setting_obj.widget)
            self.widget_count += 1
            self.widget_size = setting_obj.widget.size

        self.bind(on_touch_down=self._on_touch_down)
        if self.widget_count > 0:
            self.scrollview.bind(size=self.on_size)
        else:
            logger.warning(f'Created settings panel for empty category {panel_name} with no widgets...')

    def on_size(self, w, m):
        max_widget_vertical = int(self.scrollview.size[1] / self.widget_size[1])
        min_horizontal = math.ceil(self.widget_count / max_widget_vertical)
        self.settings_frame.set_size(x=self.widget_size[0] * min_horizontal)
        self.scrollview.do_scroll_x = (min_horizontal > 2)

    def _on_touch_down(self, w, m):
        if m.button not in {'scrollup', 'scrolldown'}:
            return
        if self.scrollview.do_scroll_x and self.collide_point(*m.pos):
            if m.button == 'scrollup':
                self.scrollview.scroll_x = minmax(0, 1, self.scrollview.scroll_x + SCROLL_SENS)
            elif m.button == 'scrolldown':
                self.scrollview.scroll_x = minmax(0, 1, self.scrollview.scroll_x - SCROLL_SENS)
