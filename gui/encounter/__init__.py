
class EncounterViewComponent:
    def __init__(self, enc=None, **kwargs):
        if enc is None:
            raise RuntimeError(f'{self} __init__ expecting enc parameter')
        self.enc = enc

    @property
    def api(self):
        return self.enc.api
