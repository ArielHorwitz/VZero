import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from nutil.kex import widgets
from data import resource_name, APP_COLOR, BASE_RESOLUTION, INFO_STR
from data.load import RDF
from data.settings import PROFILE
from data.assets import Assets

from gui.api import SpriteLabel as APISpriteLabel
from gui.common import Stack, SpriteLabel, SpriteTitleLabel


class HelpGUI(widgets.AnchorLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.make_bg((1,1,1,1))
        self._bg.source = Assets.get_sprite('ui.home')

        self.main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        self.main_frame.make_bg((0,0,0,0.75))
        self.app_control = self.main_frame.add(self.app.generate_app_control_buttons())
        self.app_control.title.text = '[b]Help[/b]'

        self.screen_names = []
        bottom_frame = self.main_frame.add(widgets.BoxLayout())
        self.button_stack = bottom_frame.add(Stack(
            name='Info buttons',
            wtype=lambda *a, **k: SpriteLabel(*a, **k),
            callback=self.button_stack_click, x=200, y=50))
        self.button_stack.set_size(x=200)

        self.panel_switch = bottom_frame.add(widgets.ScreenSwitch(transition=widgets.kvFadeTransition(duration=0.1)))
        self.set_screens(get_info_widgets())
        self.app.settings_notifier.subscribe('ui.allow_stretch', self.setting_allow_stretch)
        self.setting_allow_stretch()

    def setting_allow_stretch(self):
        if PROFILE.get_setting('ui.allow_stretch'):
            self.main_frame.set_size(hx=1, hy=1)
        else:
            self.main_frame.set_size(*BASE_RESOLUTION)

    def set_screens(self, screens):
        buttons = []
        self.screen_names = []
        sprite = Assets.BLANK_SPRITE
        for i, (name, view) in enumerate(screens):
            self.screen_names.append(name)
            title = f'[b]{name}[/b]'
            buttons.append(APISpriteLabel(sprite, title, (0,0,0,0)))
            scroll_view = widgets.ScrollView(view)
            scroll_view.make_bg(v=0, a=0.4)
            self.panel_switch.add_screen(name, view=scroll_view)
        self.panel_switch.switch_screen(screens[0][0])
        self.button_stack.update(buttons)

    def button_stack_click(self, index, button):
        if button != 'left':
            return
        self.panel_switch.switch_screen(self.screen_names[index])
        Assets.play_sfx('ui.select', volume='ui')


def get_info_widgets():
    return [
        *rdf2info(RDF.from_str(INFO_STR)),
        *rdf2info(RDF.from_file(RDF.CONFIG_DIR / 'help.rdf')),
        ('Scaling table', widgets.Image(allow_stretch=True, source=Assets.get_sprite('ui.info1'))),
        ('Scaling table long', widgets.Image(allow_stretch=True, source=Assets.get_sprite('ui.info2'))),
    ]


def rdf2info(rdf):
    info_widgets = []
    logger.info(f'rdf2info source: {rdf}')
    for panel, data in rdf.items():
        panel_widget = widgets.DynamicHeight()
        sl = SpriteLabel(Assets.BLANK_SPRITE, f'[b]{panel}[/b]', bg_mask_color=APP_COLOR)
        sl.set_size(y=50)
        panel_widget.add(sl)
        pstr = '\n'.join(data.default.positional) + '\n'
        panel_widget.add(widgets.FixedWidthLabel(text=pstr, markup=True))
        for subpanel, subpanel_data in data.items():
            sl = SpriteLabel(Assets.BLANK_SPRITE, f'[b]{subpanel}[/b]', bg_mask_color=APP_COLOR)
            sl.set_size(y=50)
            panel_widget.add(sl)
            pstr = '\n'.join(subpanel_data.positional) + '\n'
            panel_widget.add(widgets.FixedWidthLabel(text=pstr, markup=True))
        info_widgets.append((panel, panel_widget))
    return info_widgets
