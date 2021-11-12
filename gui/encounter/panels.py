from nutil.kex import widgets
from gui.encounter import EncounterViewComponent
from nutil.display import njoin, make_title
from data.load import Assets
from nutil.time import RateCounter, humanize_ms


class InfoPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        panel = self.add(widgets.BoxLayout(orientation='vertical'))
        panel.set_size(x=250, y=700)

        pic_panel = panel.add(widgets.BoxLayout()).set_size(250, 250)
        with panel.canvas:
            self.info_pic = widgets.Image(allow_stretch=True, size=(250, 250))

        self.info_label = panel.add(widgets.Label()).set_size(x=250)

        self.selected_unit = 0

    def select_unit(self, uid):
        self.selected_unit = uid

    def update(self):
        unit = self.api.units[self.selected_unit]

        self.info_label.text = njoin([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            f'{self.api.pretty_stats(self.selected_unit)}',
            make_title(f'Status', length=30),
            f'{self.api.pretty_statuses(self.selected_unit)}',
            make_title(f'Cooldown', length=30),
            f'{self.api.pretty_cooldowns(self.selected_unit)}',
            f'unit.debug_str >>',
            f'{unit.debug_str[:30]}',
        ])

        self.info_pic.pos=(self.to_local(
            self.pos[0], self.pos[1]+self.size[1]-self.info_pic.size[1]))
        self.info_pic.source = Assets.get_sprite('unit', unit.sprite)


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        main_panel = self.add(widgets.BoxLayout(orientation='vertical'))
        main_panel.set_size(x=250, y=500)

        self.info_label = main_panel.add(widgets.Label())

    def update(self):
        timer_strs = []
        for tname, timer in (*self.enc.timers.items(), *self.api.timers.items()):
            if isinstance(timer, RateCounter):
                timer_strs.append(f'- {tname}: {timer.mean_elapsed_ms:.3f} ms')

        self.info_label.text = njoin([
            make_title('Debug', length=30),
            f'Game time: {humanize_ms(self.api.elapsed_time_ms)} ({self.api.tick})',
            f'FPS: {self.app.fps.rate:.1f} ({self.app.fps.mean_elapsed_ms:.1f} ms)',
            *timer_strs,
            f'Map size: {self.api.map_size}',
            f'Map zoom: x{self.enc.zoom_level:.2f} ({self.enc.upp:.2f} u/p)',
            f'Units: {self.api.get_live_monster_count()} (drawing: {self.enc.sub_frames["sprites"].drawn_count})',
            f'vfx count: {len(self.api.get_visual_effects())}',
        ])
