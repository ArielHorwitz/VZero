
DEFAULT_HITBOX = 20


class Unit:
    def __init__(self, api, uid, allegience,
                 name=None, hitbox=DEFAULT_HITBOX,
                 internal_name=None, params=None,
                 ):
        self.__uid = uid
        self.__internal_name = internal_name
        self.name = 'Unnamed unit' if name is None else name
        # self.hitbox = hitbox
        self.allegience = allegience
        self.color = (1, 1, 1)
        self.setup(api, **params)

    def setup(self, api, **params):
        pass

    def poll_abilities(self, api):
        return None

    @property
    def uid(self):
        return self.__uid

    @property
    def internal_name(self):
        return self.__internal_name

    @property
    def sprite(self):
        return self.internal_name

    @property
    def debug_str(self):
        return f'{self} debug str undefined.'
