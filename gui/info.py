import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from nutil.kex import widgets
from data import resource_name, APP_COLOR, BASE_RESOLUTION
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

        main_frame = self.add(widgets.BoxLayout(orientation='vertical'))
        main_frame.set_size(*BASE_RESOLUTION)
        main_frame.make_bg((0,0,0,0.5))
        self.app_control = main_frame.add(self.app.generate_app_control_buttons())
        self.app_control.title.text = '[b]Help[/b]'

        self.buttons = []
        bottom_frame = main_frame.add(widgets.BoxLayout())
        bottom_frame.make_bg((0,0,0,0.75))
        self.button_stack = bottom_frame.add(Stack(
            wtype=lambda *a, **k: SpriteLabel(*a, **k),
            callback=self.button_stack_click, x=200, y=50))
        self.button_stack.set_size(x=200)

        self.panel_switch = bottom_frame.add(widgets.ScreenSwitch(transition=widgets.kvFadeTransition(duration=0.1)))
        self.set_screens(get_info_widgets())

    def set_screens(self, screens):
        self.buttons = []
        sprite = Assets.BLANK_SPRITE
        for i, (name, view) in enumerate(screens):
            name = f'[b]{name}[/b]'
            self.buttons.append(APISpriteLabel(sprite, name, (0,0,0,0)))
            self.panel_switch.add_screen(name, view=view)
            if i == 1:
                self.panel_switch.switch_screen(name)
        self.button_stack.update(self.buttons)

    def button_stack_click(self, index, button):
        if button != 'left':
            return
        self.panel_switch.switch_screen(self.buttons[index].text)
        Assets.play_sfx('ui.select', volume='ui')


_DEFAULT_INFO_STR = """
=== VZero
Welcome to VZero. I appreciate your help in testing this early version of the game [b]:)[/b]
~
[u]The game is in early alpha and not intended for public distribution.[/u]
~
This software enables and encourages user modifications for personal use. The developers take no responsibility for user directed content. The software and associated content is provided "as is", without warranty of any kind, express or implied.

-- Software
[b]© 2021-2022, all rights reserved by Ariel Horwitz.[/b]
Redistribution of this software is prohibited without explicit written permission.
~
Written in python with kivy (https://github.com/kivy/kivy)
--- Art
While there are many public domain contributions, redistribution of [i]proprietary[/i] artwork is prohibited without explicit written permission.
~
[b]Yisrael Hessler[/b] - https://github.com/imcrazeegamer
[b]Orr Didi[/b] - https://scardust.co
"""

def get_info_widgets():
    return [
        *rdf2info(RDF.from_str(_DEFAULT_INFO_STR)),
        *rdf2info(RDF.from_file(RDF.CONFIG_DIR / 'help.rdf')),
        ('Scaling table', widgets.Image(allow_stretch=True, source=Assets.get_sprite('ui.info1'))),
        ('Scaling table long', widgets.Image(allow_stretch=True, source=Assets.get_sprite('ui.info2'))),
    ]

def rdf2info(rdf):
    info_widgets = []
    logger.info(f'rdf2info rdf: {rdf}')
    for panel, data in rdf.items():
        panel_widget = widgets.BoxLayout(orientation='vertical')
        logger.info(f'rdf2info {panel} data: {data}')
        pstr = '\n'.join(data.default.positional)
        panel_widget.add(SpriteTitleLabel(Assets.BLANK_SPRITE, f'[b]{panel}[/b]', pstr, top_bg=APP_COLOR))
        for subpanel, subpanel_data in data.items():
            pstr = '\n'.join(subpanel_data.positional)
            panel_widget.add(SpriteTitleLabel(Assets.BLANK_SPRITE, f'[b]{subpanel}[/b]', pstr, top_bg=APP_COLOR))
        info_widgets.append((panel, panel_widget))
    return info_widgets
