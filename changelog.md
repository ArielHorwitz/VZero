
# v0.005
###### Engine
- Encounter pause menu, with ability descriptions
- Temporarily removed leaving encounters (bugs to be fixed)

###### Mods
- Abilities can now determine how the GUI represents them.
  - Override the `gui_state` method and return a string and rgba color.
- Exposed the `dmod` feature to API (temporary extra deltas on stats).
  - This should allow basic temporary regen/degen mechanics.


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
