
# v0.007
- GUI improvements
- Base mod balance:
  - New map
  - Respawn
  - Items


# v0.006
###### Engine
- GUI improvements and optimizations

###### Mods
- New menu for mods (shops and items!)


# v0.005
###### Engine
- Renamed project/engine to `VZero`
- Encounter pause menu, with ability descriptions
- Temporarily disabled leaving encounters (bugs to be fixed)
- Integrated nutil library, organized settings and assets
- Automated release procedure - expecting binaries on a regular basis
- RDF format utility - for parsing from a human-readable format

###### Mods
- Mods now generate the map (background and units)
- Abilities can now determine how the GUI represents them.
  - Override the `gui_state` method and return a string and rgba color.
- Exposed the `dmod` feature to API (temporary extra deltas on stats).
  - This should allow basic temporary regen/degen mechanics.
  - This feature probably requires more to make it interestingly usable.


# v0.004
- Added mod support. No documentation though so good luck...
- Units, abilities, and more are now the domain of mods.
  - Removed most default mechanics (only position, hitbox and hp are now default)
  - Auto attack removed, since no default attack


# v0.003
- Added changelog ;)
- Added config folder, with settings and balance-related stats in plaintext
- Attack will now set target as preferred and auto attack them.

### Homebrew balance
You may now create new and change existing units and abilities without code!

- All units and their stats have been moved to the `config/unit.bal` file.
- All abilities and their stats have been moved to the `config/abilities.bal` file.
- Beware and make a backup, as misformatting may break game loading.

> With great power comes great responsibility.


# v0.002
- Code cleaning

# v0.001
- Realtime play
