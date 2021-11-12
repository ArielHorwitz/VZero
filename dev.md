### Long Term Goals
- Objectives bosses
  - Reward with acceses to new abilities and items
- Map features - color aura biomes, fountains, shops, hazards


### Codebase Cleanup
- `Mechanics` modularization
  - allow loading multiple bal files for units/abilities
  - api `find_enemy_target` should be in mechanics

### Dev
- Ability types not listed in console on load

### Known bu-- I mean features
- Right click hold only works when moving mouse
- HP bar sprites drawn in wrong order (Each unit+hpbar instead of units then hp bars)
- SFX cannot be played for ticks, needs instant call

### Future features
- abilities need to have `check_castable` method, returns true if can be cast right now, disregarding targets (for UI)
- `HUD` touchup
- Popup mode/menu for UI clicks
- Ability hotkeys and bar need to be sortable
- Respawning / death feedback

### Potential Optimizations
- Drawing entire map, possibly hindering performance
  - Need to remove instructions from canvas and readd them
- Agency `poll_abilities` should have multiple resolutions (per 10 ticks, per 100 ticks, etc.)
