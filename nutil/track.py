
import collections
from nutil.vars import is_iterable

class TrackCache(collections.defaultdict):
    """
    A TrackCache is designed to associate TrackVars with callbacks.
    Simply register callbacks to source names, and when checked the TrackCache
    will call them if their source (TrackVar) has changed or been flagged.
    Defaultdict allows us to automatically make a TrackVar for every source
    entry (with a source value of None - still allowing for flagging), however
    to set the actual source of the TrackVar call register_source().
    """
    TrackvarCalls = collections.namedtuple('TrackvarCalls', ['tvar', 'calls'])
    def __init__(self, value=None):
        super().__init__(lambda v=value: TrackCache.TrackvarCalls(tvar=TrackVar(v), calls=set()))

    def flag(self, sname):
        self[sname].tvar.flag()

    def flag_all(self):
        for sname in self:
            self[sname].tvar.flag()

    def register(self, sname, value_source=None, callback=None, debug=False):
        if value_source is None and callback is None:
            raise ValueError(f'{self} register() wants either a value_source or a callback (else it has no effect)')
        if value_source:
            self.register_source(sname, value_source, debug)
        if callback:
            self.register_call(sname, callback)

    def register_source(self, sname, value_source, debug=False):
        self[sname][0].ref = value_source
        self[sname][0]._debug = debug

    def register_sources(self, sources):
        for sname, source in sources.items():
            self.register_source(sname, source)

    def register_call(self, sname, callback):
        if callable(callback):
            self[sname][1].add(callback)
        elif is_iterable(callback):
            for call in callback:
                assert callable(call)
                self[sname][1].add(call)
        else:
            raise ValueError(f'Call must contain callable(s) (got: {callback})')

    def register_calls(self, calls):
        for sname, call in calls.items():
            self.register_call(sname, call)

    def check(self, force=False, debug=False, skip_debug=tuple(), debug_calls=False):
        full_refresh = True if force else self['_force_full_refresh'][0].check()
        if full_refresh:
            print(f'Full refresh (force callbacks) for {self}')
        # Collect all calls to be made without duplicates
        all_calls = set()
        for vname, (var, calls) in self.items():
            if not full_refresh:
                if var.check():
                    if debug and vname not in skip_debug:
                        print(f'{self} triggered {vname}: {var} for calls: {calls}')
                    all_calls.update(calls)
            else:
                var.reset()
                all_calls.update(calls)
        # Call all
        for call in all_calls:
            if debug_calls:
                print(f'{self} calling: {call}')
            call()

    def ref(self, sname):
        return self[sname].tvar.ref

    def __repr__(self):
        return f'<TrackCache: {len(self)} TrackVars>'

    def calls(self, sname):
        if sname in self:
            return self[sname][1]

    def __getattr__(self, sname):
        if sname in self:
            return self[sname][0]

    def __setattr__(self, sname, value_source):
        self.register_source(sname, value_source)

    @property
    def _dict(self):
        return {k:v for k,v in self.items()}


class TrackVar:
    """
    A TrackVar is an object desgined to store some source of value which it will cache to keep track of changes to said value. A check() call will return if the value has changed since the last check. The most consistent way to refer to the source's value is to address the myTrackVar.ref attribute. Setting this .ref attribute will set the source of the value.

    The source can be a normal object or it can be a callable in which case the TrackVar's value will be the source's return value.
    The flag() method allowing to trigger the same effect as if the source's value has changed - the next check() call will return True. The reset() method will supress the flag effect.
    The check() method will check if the source's value has changed (or if the flag has been raised). If it has, it will reset the flag and return True.
    """
    def __init__(self, source=None, debug=False):
        self._flag = False
        self._source = source
        self._cache = self.ref
        self._debug = debug

    def flag(self):
        self._flag = True
        if self._debug:
            print(f'{self} flagged.')

    @property
    def ref(self):
        if callable(self._source):
            return self._source()
        return self._source

    @ref.setter
    def ref(self, value):
        self._source = value

    @staticmethod
    def equal_op(v1, v2):
        try:
            return (v1 == v2) is True
        except ValueError:
            return False

    def check(self, silent=False):
        if not self.equal_op(self._cache, self.ref) or self._flag:
            if self._debug:
                print(f'{self} triggered.')
            if silent is False:
                self.reset()
            return True
        return False

    def reset(self):
        self._cache = self.ref
        self._flag = False
        if self._debug:
            print(f'{self} reset.')

    def __repr__(self):
        return f'<TrackVar {self.ref} ({self._cache}/{self._flag})>'
