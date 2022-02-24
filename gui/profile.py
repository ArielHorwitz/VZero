import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from nutil.kex import widgets
from data import BASE_RESOLUTION, APP_COLOR
from data.settings import PROFILE
from data.assets import Assets

from gui.api import SpriteLabel as APISpriteLabel
from gui.common import Stack, SpriteLabel


class ProfileGUI(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui.home')

        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.set_size(*BASE_RESOLUTION)
        main_frame.make_bg((0,0,0,0.5))
        self.app_control = main_frame.add(self.app.generate_app_control_buttons())
        self.app_control.title.text = '[b]Profile[/b]'

        self.buttons = []
        bottom_frame = main_frame.add(widgets.BoxLayout())
        bottom_frame.make_bg((0,0,0,0.75))
        self.button_stack = bottom_frame.add(Stack(
            wtype=lambda *a, **k: SpriteLabel(*a, **k),
            callback=self.button_stack_click, x=200, y=50))
        self.button_stack.set_size(x=200)

        self.panel_switch = bottom_frame.add(widgets.ScreenSwitch(transition=widgets.kvFadeTransition(duration=0.1)))
        self.settings_panels = {name: SettingsPanel_(name, data) for name, data in PROFILE.settings.items()}
        self.set_screens([(panel.name, panel) for panel in self.settings_panels.values()])

    def set_screens(self, screens):
        self.buttons = []
        sprite = Assets.BLANK_SPRITE
        for i, (name, view) in enumerate(screens):
            name = f'[b]{name}[/b]'
            self.buttons.append(APISpriteLabel(sprite, name, (0,0,0,0)))
            self.panel_switch.add_screen(name, view=view)
        self.button_stack.update(self.buttons)

    def button_stack_click(self, index, button):
        if button != 'left':
            return
        self.panel_switch.switch_screen(self.buttons[index].text)
        Assets.play_sfx('ui.select', volume='ui')


class SettingsPanel_(widgets.BoxLayout):
    def __init__(self, panel_name, data, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.name = panel_name.capitalize()
        panel_title = SpriteLabel(Assets.BLANK_SPRITE, self.name, APP_COLOR)
        self.add(panel_title).set_size(y=50)

        settings_frame = self.add(widgets.GridLayout(cols=2))

        for setting_name, setting_obj in data.items():
            # swidget = widgets.Label(
            #     text=f'[b]{setting_name}: {setting_obj.value}[/b]\n{setting_obj}',
            #     markup=True,
            # )
            settings_frame.add(setting_obj.widget)
