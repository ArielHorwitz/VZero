import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from nutil.kex import widgets
from nutil.debug import format_exc
from nutil.vars import modify_color
from nutil.file import file_dump, file_load
from data.load import RDF
from data.default_settings import DEFAULT_SETTINGS_STR


class Profile:
    def __init__(self):
        self.callbacks = set()
        self.__default_settings = RDF.from_str(DEFAULT_SETTINGS_STR)
        logger.info(f'Found default settings: {self.__default_settings}')
        """
        Create settings objects. Two settings environments: proper and modified.
        Proper settings represent the actual values for the application.
        Savefile should always represent settings proper.
        Modified settings represent values the user is modifying and can be changed with no effect until saving.
        Modified settings must be applied to settings proper for effect.
        """
        # Create settings objects, along with defaults
        self.settings_proper = {}
        self.settings_modified = {}
        for category, cdata in self.__default_settings.items():
            self.settings_proper[category] = {}
            self.settings_modified[category] = {}
            stypes = cdata['types'] if 'types' in cdata else {}
            for setting_name, default in cdata.default.items():
                if setting_name in stypes:
                    if ', ' in stypes[setting_name]:
                        stype, *args = stypes[setting_name].split(', ')
                    else:
                        stype = stypes[setting_name]
                        args = []
                    setting_cls = _SETTING_TYPES[stype]
                else:
                    setting_cls = HotkeySetting if 'hotkey' in category.lower() else StringSetting
                    args = []
                logger.debug(f'Loading setting: {setting_name} from category {category} with default: {default}, resolved as {setting_cls.stype}')
                setting = setting_cls(setting_name, default, args)
                self.settings_proper[category][setting_name] = setting
                setting_modified = setting_cls(setting_name, default, args, anchor=setting)
                self.settings_modified[category][setting_name] = setting_modified
                logger.info(f'Loaded: {setting}')
        # Load user settings from file
        self._load_from_file()
        # Set the modified settings to match settings proper
        self._transfer_setting_env(self.settings_proper, self.settings_modified)

    def register_notifications(self, callback):
        assert callable(callback)
        self.callbacks.add(callback)
        logger.info(f'Registered for notifications: {callback}')

    def _notify(self, differences):
        for callback in self.callbacks:
            logger.debug(f'Notifying new settings to: {callback}')
            callback(differences)

    @property
    def gui_settings(self):
        return self.settings_modified

    def cancel_changes(self):
        logger.info(f'Canceling settings modifications...')
        self._transfer_setting_env(self.settings_proper, self.settings_modified)

    def save_changes(self):
        diff = self.modified_diff
        logger.info(f'Applying modified settings: {diff}')
        if diff:
            self._transfer_setting_env(self.settings_modified, self.settings_proper)
            self._transfer_setting_env(self.settings_proper, self.settings_modified)
        logger.info(f'Saving settings...')
        self._save_to_file()
        if diff:
            self._notify(diff)

    def reset_to_defaults(self):
        logger.info(f'Reseting settings to default values...')
        self._reset_setting_env(self.settings_modified)

    @property
    def modified_diff(self):
        return self._diff_env(self.settings_modified, self.settings_proper)

    @staticmethod
    def _diff_env(env_1, env_2):
        differences = set()
        for category_name, settings_category in env_1.items():
            for setting_name, setting in settings_category.items():
                if setting.diff(env_2[category_name][setting_name]):
                    differences.add(f'{category_name}.{setting_name}')
        return differences

    @staticmethod
    def _reset_setting_env(env):
        for category_name, settings_category in env.items():
            for setting_name, setting in settings_category.items():
                setting.reset()

    @staticmethod
    def _transfer_setting_env(source, target):
        for category_name, settings_category in source.items():
            for setting_name, setting in settings_category.items():
                target[category_name][setting_name].set_value(setting.value)

    def _load_from_file(self):
        self._reset_setting_env(self.settings_proper)
        user_settings = RDF.from_file(RDF.CONFIG_DIR / 'settings.rdf')
        logger.info(f'Loading user-defined settings: {user_settings}')
        for category_name, settings_category in self.settings_proper.items():
            if category_name not in user_settings:
                continue
            category_user = user_settings[category_name].default
            for setting_name, setting in settings_category.items():
                if setting_name in category_user:
                    v = category_user[setting_name]
                    setting.value = setting.from_str(v)

    def _save_to_file(self):
        rdf_lines = ['']
        for category_name, settings_category in self.settings_proper.items():
            rdf_lines.append(f'=== {category_name}')
            for setting_name, setting in settings_category.items():
                if setting.not_default:
                    rdf_lines.append(f'{setting_name}: {setting.to_str(setting.value)}')
            rdf_lines.append('')
        rdf_lines.append('')
        rdf_str = '\n'.join(rdf_lines)
        logger.info(f'Exporting user-defined settings: {rdf_str}')
        file_dump(RDF.CONFIG_DIR / 'settings.rdf', rdf_str)

    def get_setting(self, full_setting_name):
        category, setting = full_setting_name.split('.')
        return self.settings_proper[category][setting].value

    def set_setting(self, full_setting_name, value):
        category, setting = full_setting_name.split('.')
        self.cancel_changes()
        self.settings_modified[category][setting].set_value(value)
        self.save_changes()

    def toggle_setting(self, full_setting_name):
        v = not self.get_setting(full_setting_name)
        self.set_setting(full_setting_name, v)


_SETTINGS_IM = widgets.InputManager()
_SETTINGS_IM.deactivate()


class Setting:
    def __init__(self, name, default, args, anchor=None):
        self.name = name.capitalize().replace('_', ' ')
        self.args = args
        self.parse_args(args)
        self.__anchor = anchor
        reconverted = self.to_str(self.from_str(default))
        if default != reconverted:
            logger.warning(f'Setting {name} default value to_str and from_str non-commutative {default} != {reconverted}')
        self.__default_str = default
        self.__value = self.from_str(default)
        self.__value_str = self.to_str(self.__value)
        self.__cls_widget = None
        self.__widget = None
        self.__widget_label = None
        self.set_value(self.__value)

    def parse_args(self, args):
        pass

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, new_value):
        self.set_value(new_value, trigger=True)

    def set_value(self, new_value, trigger=True):
        logger.debug(f'Setting value: {new_value} for {self} trigger: {trigger}')
        self.__value_str = self.to_str(new_value)
        self.__value = self.from_str(self.__value_str)
        if self.__value_str != self.to_str(self.__value):
            raise ValueError(f'{self} to_str and from_str non-commutative {self.__value_str} != {self.to_str(self.__value)}')
        self.set_widget_label()
        if trigger:
            logger.debug(f'Triggered on_set: {self}')
            self.on_set()

    def widget_set_value(self, new_value):
        self.set_value(new_value, trigger=False)

    def on_set(self):
        pass

    def reset(self):
        self.set_value(self.default)

    @property
    def default(self):
        return self.from_str(self.__default_str)

    @property
    def as_str(self):
        return self.__value_str

    @property
    def not_default(self):
        return self.__default_str != self.__value_str

    def __repr__(self):
        return f'<{self.stype.capitalize()}Setting "{self.name}": {self.__value} {type(self.__value)} (def_str:{self.__default_str})>'

    def display_value(self, value):
        return self.to_str(value)

    def diff(self, setting):
        assert isinstance(setting, Setting)
        return self.as_str != setting.as_str

    # Widget
    @property
    def widget(self):
        if self.__widget is None:
            self.__widget, self.__widget_label, self.cls_anchor = self.__make_widget()
            self.set_widget_label()
        return self.__widget

    @property
    def cls_widget(self):
        if self.__cls_widget is None:
            self.__cls_widget = self.make_cls_widget()
        return self.__cls_widget

    def make_cls_widget(self):
        w = widgets.Label(text=self.display_value(self.value), markup=True)
        w.make_bg((0,0,0))
        return w

    def __make_widget(self):
        widget = widgets.BoxLayout()
        widget.set_size(x=400, y=50)
        widget.bind(on_touch_down=self.on_touch_down)
        label_text = f'[b][u]{self.name}[/u][/b]'
        label = widgets.Label(text=label_text, markup=True)
        widget.add(label)
        anchor = widget.add(widgets.AnchorLayout(padding=(5, 5)))
        anchor.add(self.cls_widget)
        return widget, label, anchor

    def on_touch_down(self, w, m):
        if m.button != 'right' or not self.not_default:
            return False
        if w.collide_point(*m.pos):
            self.reset()
            return True

    def set_widget_label(self, text=None):
        w = self.widget
        if text is None:
            text = self.widget_label
        if text:
            text = f'\n{text}'
        self.__widget_label.text = f'[b][u]{self.name}[/u][/b]{text}'
        if self.__anchor is not None and self.diff(self.__anchor):
            self.__widget_label.make_bg((0.5,0,0,0.5))
        elif self.not_default:
            self.__widget_label.make_bg((0,0,0.5,0.5))
        else:
            self.__widget_label.make_bg((0,0,0,0))

    @property
    def widget_label(self):
        return f'{self.display_value(self.value)}'


class StringSetting(Setting):
    stype = 'string'
    widget_label = ''

    def from_str(self, s):
        return str(s)

    def to_str(self, value):
        return str(value)

    def make_cls_widget(self):
        return widgets.Entry(
            on_text=self.__on_text,
            background_color=(0,0,0,1),
            foreground_color=(1,1,1,1),
        )

    def on_set(self):
        self.cls_widget.text = self.to_str(self.value)

    def __on_text(self, text):
        self.cls_widget.background_color = (0, 0, 0, 0.75)
        try:
            self.widget_set_value(self.to_str(text))
        except Exception as e:
            logger.info(f'Failed to set StringSetting entry:\n{format_exc(e)}')
            self.cls_widget.background_color = (0.5, 0, 0, 1)


class FloatSetting(StringSetting):
    stype = 'float'
    widget_label = ''
    def parse_args(self, args):
        self.min = float(args[0]) if len(args) > 0 else 0
        self.max = float(args[1]) if len(args) > 1 else float('inf')

    def to_str(self, value):
        value = round(float(value),3)
        assert self.min <= value <= self.max
        return str(value)

    def from_str(self, s):
        return round(float(s),3)


class ColorSetting(Setting):
    stype = 'color'
    def from_str(self, s):
        r = modify_color(tuple(float(_) for _ in s.split(', ')))
        r = tuple(round(float(_),3) for _ in r)
        assert all([0<=_<=1 for _ in r])
        return r

    def to_str(self, value):
        return ', '.join(f'{_:.2f}' for _ in value)

    def make_cls_widget(self):
        w = widgets.ColorSelect(callback=self._on_color)
        w.set_color(self.value)
        return w

    def _on_color(self, color):
        self.widget_set_value(color)

    def on_set(self):
        self.cls_widget.set_color(self.value)
        self.cls_anchor.make_bg((.5,.5,.5,1))

    widget_label = ''
    def display_value(self, value):
        return ', '.join([f'{round(_*255)}' for _ in value])


class SliderSetting(Setting):
    stype = 'slider'
    def from_str(self, s):
        r = round(float(s), 3)
        assert 0 <= r <= 1
        return r

    def to_str(self, value):
        value = round(float(value),3)
        assert 0 <= value <= 1
        return str(value)

    def make_cls_widget(self):
        w = widgets.Slider(
            value=self.value,
            on_value=self._on_value,
        )
        return w

    def _on_value(self, value):
        self.widget_set_value(self.cls_widget.value)

    def on_set(self):
        self.cls_widget.value = self.value

    def display_value(self, value):
        return f'{round(value*100)}%'


class ChoiceSetting(Setting):
    stype = 'choice'
    widget_label = ''

    def from_str(self, value):
        return str(value)

    def to_str(self, value):
        v = str(value)
        assert v in self.args
        return v

    def _click_choice(self, index, label):
        self.widget_set_value(label)

    def make_cls_widget(self):
        w = widgets.DropDownSelect(callback=self._click_choice)
        w.set_options(self.args)
        return w

    def on_set(self):
        self.cls_widget.text = self.value

    def display_value(self, value):
        return value


class SizeSetting(ChoiceSetting):
    stype = 'size'
    widget_label = ''
    def from_str(self, value):
        return tuple(float(_) for _ in value.split('×'))

    def to_str(self, value):
        v = '×'.join(str(round(_)) for _ in value)
        assert v in self.args
        return v

    def _click_choice(self, index, label):
        self.widget_set_value(self.from_str(label))


    def make_cls_widget(self):
        w = widgets.DropDownSelect(callback=self._click_choice)
        w.set_options(self.args)
        return w

    def on_set(self):
        self.cls_widget.text = self.display_value(self.value)

    def display_value(self, value):
        return self.to_str(value)


class BooleanSetting(Setting):
    stype = 'bool'
    widget_label = ''
    def from_str(self, s):
        return bool(float(s))

    def to_str(self, value):
        return str(int(value))

    def display_value(self, value):
        return str(value)

    def make_cls_widget(self):
        w = widgets.CheckBox(active=self.value)
        w.bind(on_touch_down=self._on_touch_down)
        return w

    def _on_touch_down(self, w, m):
        if not m.button == 'left' or not self.cls_widget.collide_point(*m.pos):
            return False
        self.set_value(not self.cls_widget.active)
        return True

    def on_set(self):
        self.cls_widget.active = self.value


class HotkeySetting(Setting):
    stype = 'hotkey'
    widget_label = ''
    def from_str(self, s):
        return str(s)

    def to_str(self, value):
        return str(value)

    def on_set(self):
        self.cls_widget.text = self.display_value(self.value)

    def make_cls_widget(self):
        w = widgets.ToggleButton()
        w.bind(state=self._on_state)
        return w

    def _on_state(self, *a):
        if self.cls_widget.active:
            _SETTINGS_IM.activate()
            _SETTINGS_IM.record(on_release=self._end_record, on_press=self._new_record)

    def _new_record(self, keys):
        self.cls_widget.text = self.display_value(keys)

    def _end_record(self, keys):
        self.cls_widget.active = False
        _SETTINGS_IM.deactivate()
        self.widget_set_value(keys)


_SETTING_TYPES_LIST = (
    StringSetting,
    ChoiceSetting,
    SizeSetting,
    BooleanSetting,
    FloatSetting,
    SliderSetting,
    HotkeySetting,
    ColorSetting,
)
assert len(_SETTING_TYPES_LIST) == len(set(scls.stype for scls in _SETTING_TYPES_LIST))
_SETTING_TYPES = {scls.stype: scls for scls in _SETTING_TYPES_LIST}


PROFILE = Profile()
