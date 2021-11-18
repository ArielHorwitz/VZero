from logic.mechanics import import_mod_module
base = import_mod_module('abilities.base')


ABILITY_CLASSES = {
    'move': base.Move,
    'barter': base.Barter,
    'attack': base.Attack,
    'buff': base.Buff,
    'consume': base.Consume,
    'teleport': base.Teleport,
    'blast': base.Blast,
    'regen aura': base.RegenAura,
}
