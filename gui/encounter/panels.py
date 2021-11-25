import numpy as np
from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from nutil.display import njoin, make_title
from data.assets import Assets
from nutil.time import RateCounter, humanize_ms


class InfoPanel(widgets.AnchorLayout, EncounterViewComponent):
    BAR_WIDTH = 250
    PIC_SIZE = 175
    BOTTOM_MARGIN = 100

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.panel = panel = self.add(widgets.BoxLayout(orientation='vertical'))
        self.panel.set_size(x=self.BAR_WIDTH)

        pic_panel = panel.add(widgets.BoxLayout()).set_size(self.PIC_SIZE, self.PIC_SIZE)
        with panel.canvas:
            self.info_pic = widgets.Image(allow_stretch=True, size=(self.PIC_SIZE, self.PIC_SIZE))

        self.info_label = panel.add(widgets.Label(text_size=(self.BAR_WIDTH, None)))

        self.selected_unit = 0

    def select_unit(self, uid):
        self.selected_unit = uid

    def update(self):
        self.panel.set_size(x=self.BAR_WIDTH, y=self.height-self.BOTTOM_MARGIN)
        self.panel.pos = self.info_label.pos = self.x+5, self.y+self.BOTTOM_MARGIN

        player_dist = self.api.get_distances(self.api.get_position(0))[self.selected_unit]
        unit = self.api.units[self.selected_unit]
        self.info_label.text = njoin([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            f'{self.api.pretty_stats(self.selected_unit)}',
            make_title(f'Status', length=30),
            f'{self.api.pretty_statuses(self.selected_unit)}',
            make_title(f'Cooldown', length=30),
            f'{self.api.pretty_cooldowns(self.selected_unit)}',
            make_title(f'Debug', length=30),
            f'{unit.debug_str}',
            f'Distance: {player_dist:.1f}',
            f'Action phase: {unit.uid % self.api.e.AGENCY_PHASE_COUNT}',
            f'Last action: {self.api.tick - unit._debug_last_action}',
            f'Agency: {self.api.timers["agency"][unit.uid].mean_elapsed_ms:.3f} ms',
        ])

        self.info_pic.pos = self.to_local(self.x, self.y+self.height-self.info_pic.height)
        self.info_pic.source = Assets.get_sprite('unit', unit.sprite)


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        main_panel = self.add(widgets.BoxLayout(orientation='vertical'))
        main_panel.set_size(x=250)

        self.info_label = main_panel.add(widgets.Label(valign='top'))

    def update(self):
        timer_strs = []
        for tname, timer in (*self.enc.timers.items(), *self.api.timers.items()):
            if isinstance(timer, RateCounter):
                timer_strs.append(f'- {tname}: {timer.mean_elapsed_ms:.3f} ms')

        self.info_label.text = njoin([
            make_title('Debug', length=30),
            f'Game time: {humanize_ms(self.api.elapsed_time_ms)}',
            f'Tick: {self.api.tick} +{self.api.s2ticks()} t/s',
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            *timer_strs,
            f'Map size: {self.api.map_size}',
            f'View size: {list(round(_) for _ in self.enc.view_size)}',
            f'Map zoom: x{self.enc.zoom_level:.2f} ({self.enc.upp:.2f} u/p)',
            f'Units: {self.api.get_live_monster_count()} / {self.api.unit_count} (drawing: {self.enc.sub_frames["sprites"].drawn_count})',
            f'Agency phase: {self.api.tick % self.api.e.AGENCY_PHASE_COUNT}',
            f'vfx count: {len(self.api.get_visual_effects())}',
        ])
        self.info_label.text_size = 250, self.size[1]
