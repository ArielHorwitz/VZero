## TODO

### Result Oriented
- Buffs
- AOE
- Abilities (aoe, slow, reflect)
- Ability selection before map start
- Objectives bosses
  - Reward with acceses to new abilities and items
- Map features - color aura biomes, fountains, shops, hazards

### Desired Features
- Prolonged effects / buffs
  - Or delayed effects to allow temporary buffs (buff then debuff)
- Aura effects: method `uids_in_radius` for aoes and auras
  - Map features: foundtains, shops (using auras)
- Respawning
- Real time-translations: methods `ticks2ms`, and `ms2ticks` for Agency and VFX
- Packaging for Windows

### Bugfixes
- Right click hold only works when moving mouse
  - Should release should release SFX
- Spamming ability hotkeys repeats SFX


### Long term issues
- Drawing entire map, possibly hindering performance
  - Need to remove instructions from canvas and readd them
