import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

import collections
import numpy as np
from nutil.vars import modify_color
from data import resource_name


GUI_STATE = collections.namedtuple('GUI_STATE', ('string', 'color'))


class Ability:
    color = (0.5, 0.5, 0.5, 1)

    def __init__(self, aid, name, stats):
        self.name = name
        self.aid = aid
        self.setup(**stats)

    def setup(self, **stats):
        pass

    @property
    def sprite(self):
        return resource_name(self.aid.name)

    def gui_state(self, api, uid, target=None):
        # Return a tuple with a string and color for gui
        # Used for representing the state of an ability (such as cooldown)
        cd = api.get_cooldown(uid, self.aid)
        if cd > 0:
            string = f'CD: {api.ticks2s(cd):.1f}'
            color = modify_color(self.color, v=0.25)
        else:
            string = ''
            color = self.color
        return GUI_STATE(string, color)

    def cast(self, api, uid, target):
        m = f'Ability {self.aid} cast method not implemented'
        logger.error(m)
        raise NotImplementedError(m)

    def passive(self, api, uid, dt):
        pass

    @property
    def description(self):
        return f'No description available (#{self.aid})'
