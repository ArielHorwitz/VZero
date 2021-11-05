## TODO

### Result Oriented
- Organize balance and mechanics in config files
- AOE
- Abilities (aoe, slow, reflect)
- Ability selection before map start
- Objectives bosses
  - Reward with acceses to new abilities and items
- Map features - color aura biomes, fountains, shops, hazards


### Desired Features
- Agency `poll_abilities` should have multiple resolutions (per 10 ticks, per 100 ticks, etc.)
- Aura effects: method `uids_in_radius` for aoes and auras
  - Map features: foundtains, shops (using auras)
- Respawning / death feedback
- Real time-translations: methods `ticks2ms`, and `ms2ticks` for Agency and VFX
- Debug frame update breakdown
  - By draw
  - By logic
    - Ticks, Agency
  - By mainloop interval (kivy runtime between frames)
- Scale HP bar size to max hp


### Known Bugs
- Right click hold only works when moving mouse
  - Should release should release SFX
- Spamming ability hotkeys repeats SFX
- HP bar sprites drawn in wrong order (Each unit+hpbar instead of units then hp bars)


### Long term issues
- Drawing entire map, possibly hindering performance
  - Need to remove instructions from canvas and readd them
  - kvLine circles are incredibly expensive
