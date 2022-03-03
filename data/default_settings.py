DEFAULT_SETTINGS_STR = """
=== general
name: General

--- fullscreen
default: 1
type: bool

--- fullscreen_resolution
default: 1920×1080
type: size
options: 2560×1440, 1920×1080, 1600×900, 1366×768, 1600×1200, 1400×1050, 1280×960, 1152×864, 1024×768

--- fullscreen_type
default: fullscreen
type: choice
options: fullscreen, borderless

--- window_resolution
default: 1024×768
type: size
options: 2560×1440, 1920×1080, 1600×900, 1366×768, 1600×1200, 1400×1050, 1280×960, 1152×864, 1024×768

--- enable_window_offset
default: 1
type: bool
caption: automatically position the window at the offset

--- window_offset_x
default: 100.0
type: float
min: -inf

--- window_offset_y
default: 100.0
type: float
min: -inf

--- borderless_offset_x
default: 0.0
type: float
min: -inf

--- borderless_offset_y
default: 0.0
type: float
min: -inf

--- enable_hold_mouse
default: 1
type: bool
caption: holding mouse auto clicks

--- enable_hold_key
default: 0
type: bool
caption: holding keyboard auto presses



=== audio
name: Audio

--- volume_master
default: 0.5
type: slider
display_name: Master volume

--- volume_sfx
default: 1.0
type: slider
display_name: Sound effects volume

--- volume_ui
default: 0.6
type: slider
display_name: UI volume

--- volume_feedback
default: 0.75
type: slider
display_name: Feedback volume

--- volume_monster_death
default: 0.5
type: slider
display_name: Monster death volume

--- feedback_sfx_cooldown
default: 500.0
type: float
display_name: Feedback interval
caption: minimum ms between sounds



=== ui
name: UI

--- default_zoom
default: 40.0
type: float
min: 5
max: 100

--- detailed_mode
default: 0
type: bool
caption: ui shows more info

--- fullscreen_grab_mouse
default: 1
type: bool
caption: prevent mouse from escaping the window

--- auto_tooltip
default: 1
type: bool
display_name: Tooltip on hover
caption: in detailed mode

--- auto_dismiss_tooltip
default: 50.0
type: float
caption: mouse distance in pixels

--- auto_pause_shop
default: 1
type: bool
display_name: Pause when shopping

--- allow_stretch
default: 1
type: bool
display_name: UI stretch
caption: UI stretches to fit screen

--- hud_height
default: 0.5
type: slider

--- hud_width
default: 0.5
type: slider

--- fog_color
default: 0.00, 0.00, 0.00, 0.70
type: color

--- fog_size
default: 45.0
type: float
caption: calibration for custom fog

--- decoration_color
default: 1.00, 1.00, 1.00, 0.75
type: color
decoration_color
caption: color of screen decoration



=== hotkeys
name: Hotkeys

--- toggle_fullscreen
default: f11

--- toggle_play
default: spacebar

--- toggle_map
default: tab

--- toggle_detailed
default: ! alt

--- toggle_shop
default: f1

--- loot
default: z

--- alt_modifier
default: Shift
type: choice
options: Shift, Alt, Control, Super
caption: for alternative casting

--- ability_1
default: q
--- ability_2
default: w
--- ability_3
default: e
--- ability_4
default: r
--- ability_5
default: a
--- ability_6
default: s
--- ability_7
default: d
--- ability_8
default: f
--- item_1
default: 1
--- item_2
default: 2
--- item_3
default: 3
--- item_4
default: 4
--- item_5
default: 5
--- item_6
default: 6
--- item_7
default: 7
--- item_8
default: 8

--- reset_view
default: home

--- unpan
default: end

--- zoom_in
default: =

--- zoom_out
default: -

--- pan_up
default: up
--- pan_down
default: down
--- pan_left
default: left
--- pan_right
default: right

--- refresh
default: f5

--- tab1
default: ^+ f5

--- tab2
default: ^+ f6
--- tab3
default: ^+ f7
--- tab4
default: ^+ f8

--- dev1
default: ^+ f9
--- dev2
default: ^+ f10
--- dev3
default: ^+ f11
--- toggle_debug
default: ^+ f12


=== misc
name: Misc

--- dev_build*
default: 0
type: bool
display_name: Dev build
caption: for development use, requires restart

--- debug_mode
default: 0
type: bool
caption: only works in dev build

--- map_editor_mode
default: 0
type: bool
caption: show map biome cores

--- auto_log
default: 1
type: bool
caption: for extra debugging

--- log_interval
default: 3000.0
type: float
caption: in ticks



"""
