DEFAULT_SETTINGS_STR = """
=== general
default_window: fullscreen
full_resolution: 1920×1080
window_resolution: 1024×768
default_zoom: 40
enable_hold_mouse: 1
enable_hold_key: 0
dev_build: 0
auto_log: 1
log_interval: 3000

--- types
default_window: choice, fullscreen, borderless, windowed
full_resolution: size, 1920×1080, 1024×768
window_resolution: size, 1920×1080, 1024×768
default_zoom: float, 5, 100
enable_hold_mouse: bool
enable_hold_key: bool
dev_build: bool
auto_log: bool
log_interval: float

=== ui
detailed_mode: 1
auto_dismiss_tooltip: 100
auto_tooltip: 0
hud_scale: 1
decorations: 0.75
feedback_sfx_cooldown: 350
fog: 45
fog_color: 0, 0, 0, 0.6

--- types
detailed_mode: bool
auto_dismiss_tooltip: float
auto_tooltip: bool
hud_scale: slider, 0.5, 3
decorations: slider
feedback_sfx_cooldown: float
fog: float
fog_color: color


=== audio
volume_master: 0.15
volume_sfx: 1
volume_ui: 0.5
volume_feedback: 0.5
volume_monster_death: 0.4

--- types
volume_master: slider
volume_sfx: slider
volume_ui: slider
volume_feedback: slider
volume_monster_death: slider


=== hotkeys
toggle_fullscreen: f11
toggle_borderless: ! f11
toggle_menu: escape
toggle_play: spacebar
toggle_shop: f1
toggle_map: tab
toggle_detailed: ! alt

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

dev1: ^+ f9
dev2: ^+ f10
dev3: ^+ f11
dev4: ^+ f12

=== loadouts

"""
