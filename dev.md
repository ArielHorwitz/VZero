### Long Term Goals
- Objectives bosses
  - Reward with acceses to new abilities and items
- Find name for game
- Map features - color aura biomes, fountains, shops, hazards


### Base mod
- Consumables and shops
- Extend base class `Ability` for base mod
  - Taking init arguments automatically and store in dict
  - Streamlined description strings
  - Check castability method


### Known bu-- I mean features
- Hotkeys of old encounters still bound
  - Music theme sound object still controlled by old encounter object, causing multiple encounter objects to toggle play/pause
- Right click hold only works when moving mouse
  - Missing move target crosshair
- HP bar sprites draw order could be more intuitive
- SFX cannot be played for ticks, needs instant call
  - New environment system? (VFX, SFX based on player perspective)
- Ability hotkeys need to be sortable
- HUD Ability bar should check castability, not just cooldown
  - abilities need to have `check_castable` method
  - returns true if can be cast right now, optionally regarding targets
- HUD statbars could conform with sprite hp bar
- Rename bal file format


### Future features
- Implement creating every ability class with defaults (w/ name suffix filter)
- Popup mode/menu for UI clicks
- Respawning / death feedback
- Allow loading multiple bal files for units/abilities


### Potential Optimizations
- Agency `poll_abilities` - multiple time resolutions based on distance to player
