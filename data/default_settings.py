DEFAULT_SETTINGS_STR = """
=== general
fullscreen: 1
fullscreen_type: fullscreen
fullscreen_resolution: 1920×1080
window_resolution: 1024×768
window_offset_x: 100.0
window_offset_y: 100.0
borderless_offset_x: 0.0
borderless_offset_y: 0.0
enable_hold_mouse: 1
enable_hold_key: 0

--- types
fullscreen: bool
fullscreen_type: choice, fullscreen, borderless
fullscreen_resolution: size, 2560×1440, 1920×1080, 1600×900, 1366×768, 1600×1200, 1400×1050, 1280×960, 1152×864, 1024×768
window_resolution: size, 2560×1440, 1920×1080, 1600×900, 1366×768, 1600×1200, 1400×1050, 1280×960, 1152×864, 1024×768
window_offset_x: float, -inf, inf
window_offset_y: float, -inf, inf
borderless_offset_x: float, -inf, inf
borderless_offset_y: float, -inf, inf
enable_hold_mouse: bool
enable_hold_key: bool


--- display
enable_hold_mouse: hold to keep clicking
enable_hold_key: hold to keep pressing

=== audio
volume_master: 0.15
volume_sfx: 1.0
volume_ui: 0.5
volume_feedback: 0.5
volume_monster_death: 0.4

--- types
volume_master: slider
volume_sfx: slider
volume_ui: slider
volume_feedback: slider
volume_monster_death: slider


=== ui
default_zoom: 40.0
detailed_mode: 0
fullscreen_grab_mouse: 1
auto_tooltip: 1
auto_dismiss_tooltip: 100.0
hud_height: 0.5
hud_width: 0.5
fog_color: 0.00, 0.00, 0.00, 0.70
fog_size: 45.0
decoration_color: 1.00, 1.00, 1.00, 0.75
feedback_sfx_cooldown: 500.0

--- types
default_zoom: float, 5, 100
detailed_mode: bool
fullscreen_grab_mouse: bool
auto_tooltip: bool
auto_dismiss_tooltip: float
hud_height: slider
hud_width: slider
fog_color: color
fog_size: float
decoration_color: color
feedback_sfx_cooldown: float


--- display
auto_tooltip: show tooltip on hover
auto_dismiss_tooltip: in pixels
fog_size: calibration for custom fog
decoration_color: color of screen decoration
feedback_sfx_cooldown: minimum ms between sounds


=== hotkeys
toggle_fullscreen: f11
toggle_menu: escape
toggle_play: spacebar
toggle_map: tab
toggle_detailed: ! alt
toggle_shop: f1

loot: z
alt_modifier: +
ability1: q
ability2: w
ability3: e
ability4: r
ability5: a
ability6: s
ability7: d
ability8: f
item1: 1
item2: 2
item3: 3
item4: 4
item5: 5
item6: 6
item7: 7
item8: 8

reset_view: home
unpan: end
zoom_in: =
zoom_out: -
pan_up: up
pan_down: down
pan_left: left
pan_right: right

refresh: f5

tab1: ^+ f5
tab2: ^+ f6
tab3: ^+ f7
tab4: ^+ f8

dev1: ^+ f9
dev2: ^+ f10
dev3: ^+ f11
dev4: ^+ f12


--- display
alt_modifier: [i]for alternative casting[/i]

=== misc
dev_build *: 0
debug_mode: 0
map_editor_mode: 0
auto_log: 1
log_interval: 3000.0

--- types
dev_build *: bool
debug_mode: bool
map_editor_mode: bool
auto_log: bool
log_interval: float


--- display
dev_build *: requires restart
debug_mode: only works in dev build
map_editor_mode: show map biome cores
auto_log: for extra debugging
log_interval: in ticks

"""
