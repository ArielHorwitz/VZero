from logic.mechanics import import_mod_module as import_
base = import_('abilities.base')


ABILITY_CLASSES = {
    'move': base.Move,
    'barter': base.Barter,
    'attack': base.Attack,
    'buff': base.Buff,
    'consume': base.Consume,
    'teleport': base.Teleport,
    'blast': base.Blast,
    'midas': base.Midas,
    'regen aura': base.RegenAura,
    'shopkeeper': base.Shopkeeper,
    'test': base.Test,
    'map_editor_eraser': base.MapEditorEraser,
    'map_editor_toggle': base.MapEditorToggle,
    'map_editor_palette': base.MapEditorPalette,
    'map_editor_droplet': base.MapEditorDroplet,
}
