import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


from collections import namedtuple
import numpy as np
from nutil.kex import widgets
from nutil.display import njoin, make_title
from nutil.vars import minmax
from nutil.time import RateCounter, humanize_ms
from gui import cc_int, center_position
from gui.encounter import EncounterViewComponent
from data.assets import Assets
from logic.mechanics.common import *


Box = namedtuple('Box', ['box', 'sprite', 'label'])


class AgentViewer(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_selected = -1
        self.default_scale = 100 / self.api.get_stats(0, STAT.HITBOX)

        self.panel = self.add(widgets.BoxLayout(orientation='vertical'))
        self.panel.set_size(x=300, y=500)
        self.panel.make_bg((0, 0, 0, 0.3))

        self.name_label = self.panel.add(widgets.Label(valign='middle', halign='center'))
        self.name_label.set_size(y=50)

        bar_frame = self.panel.add(widgets.BoxLayout(orientation='vertical'))
        bar_values = self.api.mod_api.agent_panel_bars(0)
        bar_count = len(bar_values)
        bar_frame.set_size(y=20*bar_count)
        self.bars = [bar_frame.add(widgets.Progress()) for _ in range(bar_count)]

        self.sprite_frame = self.panel.add(widgets.BoxLayout())
        self.sprite = self.sprite_frame.add(widgets.Image(allow_stretch=True))

        boxes_frame = self.panel.add(widgets.GridLayout(cols=3))
        boxes_frame.set_size(y=140)
        self.boxes = []
        for i in range(6):
            box = boxes_frame.add(widgets.BoxLayout())
            box.set_size(y=70)
            im = box.add(widgets.Image(allow_stretch=True))
            im.set_size(x=40)
            label = box.add(widgets.Label(valign='middle'))
            self.boxes.append(Box(box, im, label))

        self.label = self.panel.add(widgets.Label(valign='top'))

    def get_sprite_size(self, uid):
        h = minmax(30, 150,
            self.api.get_stats(uid, STAT.HITBOX) * self.default_scale)
        return cc_int((h, h))

    def update(self):
        self.panel.pos = 20, self.size[1] - self.panel.size[1] - 20

        unit = self.api.units[self.enc.selected_unit]

        bar_values = self.api.mod_api.agent_panel_bars(unit.uid)
        for i, (progress, color, text) in enumerate(bar_values):
            self.bars[i].progress = progress
            self.bars[i].fg_color = color
            self.bars[i].text = text

        sprite_size = self.get_sprite_size(unit.uid)
        sprite_pos = np.array(self.sprite_frame.pos) + (np.array(self.sprite_frame.size) / 2)
        self.sprite.pos = center_position(sprite_pos, sprite_size)

        if self.last_selected != self.enc.selected_unit:
            self.redraw_new_agent()

        texts = self.api.mod_api.agent_panel_boxes_labels(unit.uid)
        for i, box in enumerate(self.boxes):
            box.label.text = texts[i]

        self.label.text = self.api.mod_api.agent_panel_label(unit.uid)
        self.label.text_size = self.label.size

    def redraw_new_agent(self):
        unit = self.api.units[self.enc.selected_unit]
        self.last_selected = self.enc.selected_unit
        self.name_label.text = unit.name
        self.sprite.source = Assets.get_sprite('unit', unit.sprite)
        self.sprite.set_size(*self.get_sprite_size(unit.uid))

        boxes = self.api.mod_api.agent_panel_boxes_sprites(unit.uid)
        for i, (category, sprite) in enumerate(boxes):
            self.boxes[i].sprite.source = Assets.get_sprite(category, sprite)


class InfoPanel(widgets.AnchorLayout, EncounterViewComponent):
    BAR_WIDTH = 400
    BAR_HEIGHT = 800
    PIC_SIZE = 175
    BOTTOM_MARGIN = 100

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.panel = panel = self.add(widgets.BoxLayout(orientation='vertical'))
        self.panel.set_size(x=self.BAR_WIDTH, y=self.BAR_HEIGHT)
        self.panel.make_bg((0.1, 0.1, 0.1, 0.25))

        pic_panel = panel.add(widgets.BoxLayout()).set_size(self.PIC_SIZE, self.PIC_SIZE)
        with panel.canvas:
            self.info_pic = widgets.Image(allow_stretch=True, size=(self.PIC_SIZE, self.PIC_SIZE))

        self.info_label = panel.add(widgets.Label(text_size=(self.BAR_WIDTH, None)))

    def update(self):
        self.panel.set_size(x=self.BAR_WIDTH, y=self.height-self.BOTTOM_MARGIN)
        self.panel.pos = self.info_label.pos = 0, self.size[1] - self.panel.size[1]

        player_dist = self.api.get_distances(self.api.get_position(0))[self.enc.selected_unit]
        unit = self.api.units[self.enc.selected_unit]
        self.info_label.text = njoin([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            f'{self.api.pretty_stats(self.enc.selected_unit)}',
            make_title(f'Status', length=30),
            f'{self.api.pretty_statuses(self.enc.selected_unit)}',
        ])

        self.info_pic.pos = self.to_local(self.x, self.y+self.height-self.info_pic.height)
        self.info_pic.source = Assets.get_sprite('unit', unit.sprite)


class DebugPanel(widgets.AnchorLayout, EncounterViewComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        main_panel = self.add(widgets.BoxLayout())
        main_panel.set_size(x=500)

        self.unit_debug = main_panel.add(widgets.Label(valign='top'))
        self.unit_debug.make_bg((0, 0, 0, 0.25))
        self.performance = main_panel.add(widgets.Label(valign='top'))
        self.performance.make_bg((0, 0, 0, 0.25))

    def update(self):
        if not self.api.dev_mode:
            self.pos = self.enc.OUT_OF_DRAW_ZONE
            return
        self.pos = 0, 0

        unit = self.api.units[self.enc.selected_unit]
        player_dist = self.api.get_distances(self.api.get_position(0))[self.enc.selected_unit]
        self.unit_debug.text = '\n'.join([
            make_title(f'{unit.name} (#{unit.uid})', length=30),
            f'{self.api.pretty_stats(self.enc.selected_unit)}',
            make_title(f'Status', length=30),
            f'{self.api.pretty_statuses(self.enc.selected_unit)}',
            make_title(f'Cooldown', length=30),
            f'{self.api.pretty_cooldowns(self.enc.selected_unit)}',
            make_title(f'Debug', length=30),
            f'{unit.debug_str}',
            f'Distance: {player_dist:.1f}',
            f'Action phase: {unit.uid % self.api.e.AGENCY_PHASE_COUNT}',
            f'Last action: {self.api.tick - unit._debug_last_action}',
            f'Agency: {self.api.timers["agency"][unit.uid].mean_elapsed_ms:.3f} ms',
        ])
        self.unit_debug.text_size = 250, self.size[1]

        timer_strs = []
        for tname, timer in (*self.enc.timers.items(), *self.api.timers.items()):
            if isinstance(timer, RateCounter):
                timer_strs.append(f'- {tname}: {timer.mean_elapsed_ms:.3f} ms')

        self.performance.text = njoin([
            make_title('Performance', length=30),
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
        self.performance.text_size = 250, self.size[1]
