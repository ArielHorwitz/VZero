
from logic.units.unit import Unit

class Treasure(Unit):
    def startup(self, api, name='Loot me!'):
        self.name = name


UNIT_TYPES = {
    'treasure': Treasure,
}
