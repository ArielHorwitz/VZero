import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from nutil.kex import widgets
from nutil.debug import format_exc
from nutil.vars import modify_color
from nutil.file import file_dump
from data import CorruptedDataError, DEV_BUILD
from data.load import RDF
from data.default_settings import DEFAULT_SETTINGS_STR


file_dump(RDF.CONFIG_DIR / 'settings-auto-generated-defaults.rdf', DEFAULT_SETTINGS_STR)


class Settings:
    DEFAULT_SETTINGS = RDF.from_str(DEFAULT_SETTINGS_STR)
    USER_SETTINGS = RDF.from_file(RDF.CONFIG_DIR / 'settings.rdf')

    @classmethod
    def reload_settings(cls):
        # cls.USER_SETTINGS = RDF.from_file(RDF.CONFIG_DIR / 'settings.rdf')
        # logger.info(f'Reloaded user-defined settings: {Settings.USER_SETTINGS}')
        pass

    @classmethod
    def get_volume(cls, category=None):
        v = 1
        if category is not None:
            v = cls.get_setting(f'volume_{category}', 'Audio')
        v *= cls.get_setting(f'volume_master', 'Audio')
        return v

    @classmethod
    def get_setting(cls, setting, category='general'):
        category = category.lower()
        return PROFILE.get_setting(category, setting)

    @classmethod
    def get_setting_old(cls, setting, category='general'):
        category = category.lower()
        try:
            return cls.USER_SETTINGS[category].default[setting]
        except Exception as e:
            return cls.DEFAULT_SETTINGS[category].default[setting]


class Profile:
    def __init__(self):
        self.__default_settings = RDF.from_str(DEFAULT_SETTINGS_STR)
        self.__user_settings = RDF.from_file(RDF.CONFIG_DIR / 'settings.rdf')
        logger.info(f'Found default settings: {self.__default_settings}')
        logger.info(f'Found user-defined settings: {self.__user_settings}')
        self.settings = {}
        for category, cdata in self.__default_settings.items():
            self.settings[category] = {}
            stypes = cdata['types'] if 'types' in cdata else {}
            category_user = self.__user_settings[category].default
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
                logger.info(f'Loading setting: {setting_name} from category {category} with default: {default}, resolved as {setting_cls.stype}')
                setting = setting_cls(setting_name, default, args)
                self.settings[category][setting_name] = setting
                logger.info(f'Default: {setting}')
                if setting_name in category_user:
                    v = category_user[setting_name]
                    logger.info(f'Found user setting for {setting_name}: {v}')
                    setting.value = setting.from_str(v)
                    logger.info(f'User setting: {setting}')

    def export(self):
        settings = RDF.from_str(self.__default_settings.export_str)

    def get_setting(self, category, setting):
        return self.settings[category][setting].value

    def get_setting_old(self, category, setting):
        assert setting in self.__default_settings[category].default
        try:
            return self.__user_settings[category].default[setting]
        except Exception as e:
            return self.__default_settings[category].default[setting]


_SETTINGS_IM = widgets.InputManager()
_SETTINGS_IM.deactivate()


class Setting:
    def __init__(self, name, default, args):
        self.name = name.capitalize().replace('_', ' ')
        self.args = args
        self.parse_args(args)
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
        logger.info(f'Setting value: {new_value} for {self} trigger: {trigger}')
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

    @property
    def default(self):
        return self.from_str(self.__default_str)

    def __repr__(self):
        return f'<{self.stype.capitalize()}Setting "{self.name}": {self.__value} {type(self.__value)} (def_str:{self.__default_str})>'

    def display_value(self, value):
        return self.to_str(value)

    # Widget
    @property
    def widget(self):
        if self.__widget is None:
            self.__widget, self.__widget_label = self.__make_widget()
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
        label_text = f'[b][u]{self.name}[/u][/b]'
        label = widgets.Label(text=label_text, markup=True)
        label.make_bg(self.color)
        widget.add(label)
        anchor = widget.add(widgets.AnchorLayout(padding=(5, 5)))
        anchor.add(self.cls_widget)
        return widget, label

    def set_widget_label(self, text=None):
        w = self.widget
        if text is None:
            text = self.widget_label
        if DEV_BUILD:
            text = f'{text} [i]default: {self.display_value(self.default)}[/i]'
        if text:
            text = f'\n{text}'
        self.__widget_label.text = f'[b][u]{self.name}[/u][/b]{text}'

    @property
    def widget_label(self):
        return f'{self.display_value(self.value)}'


class StringSetting(Setting):
    stype = 'string'
    widget_label = ''
    color = 0.5, 0.5, 0.5

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
        self.widget.make_bg((.2,.2,.2,1))
        self.cls_widget.background_color = (0, 0.5, 0, 1)
        try:
            self.widget_set_value(self.to_str(text))
        except Exception as e:
            logger.info(f'Failed to set StringSetting entry:\n{format_exc(e)}')
            self.cls_widget.background_color = (0.5, 0, 0, 1)


class FloatSetting(StringSetting):
    stype = 'float'
    widget_label = ''
    color = 0, 0.5, 0
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
    color = 0.25, 0.25, 0.25
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
        self.widget.make_bg((.5,.5,.5,1))

    widget_label = ''
    def display_value(self, value):
        return ', '.join([f'{round(_*255)}' for _ in value])


class SliderSetting(Setting):
    stype = 'slider'
    color = 0.5, 0.5, 0
    def from_str(self, s):
        r = round(float(s), 3)
        assert 0 <= r <= 1
        return r

    def to_str(self, value):
        return str(round(value,3))

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
    color = 0.25, 0, 0.25

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
    color = 0.25, 0, 0.25
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
    color = 0, 0, 0.4
    def from_str(self, s):
        return bool(float(s))

    def to_str(self, value):
        return str(int(value))

    def display_value(self, value):
        return str(value)

    def make_cls_widget(self):
        w = widgets.CheckBox(active=self.value)
        w.bind(active=self._on_toggle)
        return w

    def _on_toggle(self, *a):
        self.widget_set_value(self.cls_widget.active)

    def on_set(self):
        self.cls_widget.active = self.value


class HotkeySetting(Setting):
    stype = 'hotkey'
    widget_label = ''
    color = 0.4, 0.2, 0.2

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
