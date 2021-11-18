
### Base mod work
- Fountains
- Spawns
- Clean descriptions


### Long Term Goals
- Reward with acceses to new abilities between encounters


### VZero Engine

###### Known Bugs
- `Theme` loop seems to forget volume sometimes, leading to random music playing

###### Future features
- Old encounters still bound, causing much mayhem and chaos
  - Hotkeys of old encounters still bound - huge mess!
- Abilities need to be sortable
- `HUD statbars` could conform with sprite hp bar (and configurable by mod)
- `Settings` and `Assets` need their own modules
- Encounter should call mod for:
  - Spawning units and other initialization of the encounter
  - Resolve win condition / encounter conclusion
- `Hotkeys` widget class needs work (see known bugs)
  - Keyboard hotkeys should not be hold-able
  - Right click hold only works when moving mouse  
- `Environment system` for vfx/sfx
  - Effects based on player perspective
  - SFX cannot be played for ticks, needs instant call
  - VFX should not be redrawn every frame, continuous update instead
- `Respawning` / death feedback
- Allow loading `multiple config files` for units/abilities
  - Mod should be able to make "defaults" for abilities and units
  - Rename bal file format. RDF? (Redundant Data Format)

###### Optimizations
- Agency `poll_abilities` - multiple time resolutions based on distance to player
- `get_stats` parameters should transform axes to conform to stats table shape
