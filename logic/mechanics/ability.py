from data.load import resource_name


class Ability:
    def __init__(self, aid, name, stats):
        self.name = name
        self.aid = aid
        self.color = (0.25, 0.25, 0.25)
        self.setup(**stats)

    def setup(self, **stats):
        pass

    @property
    def sprite(self):
        return resource_name(self.aid.name)

    def cast(self, aid, uid, target):
        raise NotImplementedError(f'Ability {self.aid} cast method not implemented')

    @property
    def description(self):
        return f'No description available (#{self.aid})'
