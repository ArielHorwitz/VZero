
import time
import contextlib
import copy
import numpy as np


def humanize_ms(t, show_ms=False, show_hours=True):
    ms = int(t % 1000)
    seconds = int(t % 60_000 // 1000)
    minutes = int(t % 3_600_000 // 60_000)
    hours = int(t % 21_600_000 // 3_600_000)
    s = f'{minutes:0>2}:{seconds:0>2}'
    if show_hours:
        s = f'{hours:0>2}:{s}'
    if show_ms:
        s = f'{s}:{ms:0<3}'
    return s


def sleep(s):
    time.sleep(s)


def ping():
    """
    Generate a time value to be later used by pong.

    :return:    Time in ms
    """
    return time.time() * 1000


def pong(ping_, ms_rounding=3):
    """
    Returns the delta between ping and pong in ms.

    :param ping_:           Time from ping()
    :param ms_rounding:     No. of ms digits to round
    :return:                Float of time delta in ms
    """
    return round((time.time() * 1000) - ping_, ms_rounding)


@contextlib.contextmanager
def pingpong(desc='Pingpong', show=True, ms_rounding=3):
    """
    A context manager to record elapsed time of execution of a code block.

    :param desc:            Description of time record
    :param show:            Print to console
    :param ms_rounding:     No. of ms digits to round
    :return:                Elapsed time in ms
    """

    p = ping()
    yield p
    elapsed = pong(p, ms_rounding)
    if show:
        print(f'{desc} elapsed in {elapsed}ms')
    return elapsed


@contextlib.contextmanager
def ratecounter(r):
    """
    A context manager to record elapsed time of execution of a code block,
    using a RateCounter.

    :param r:               RateCounter object
    :return:                Elapsed time in ms
    """
    p = r.ping()
    yield p
    elapsed = r.pong()
    return elapsed


class RateCounter:
    """A simple rate counter (such as for FPS)."""

    def __init__(self, sample_size=120, starting_elapsed=1000):
        super().__init__()
        self.counter = 0
        self.last_count = ping()
        self.sample_size = sample_size
        self.sample = np.ones(self.sample_size, dtype=np.float64) * starting_elapsed
        self.__sample_index = 0

    def ping(self):
        self.last_count = ping()

    def pong(self):
        return self.tick()

    def start(self):
        self.last_count = ping()

    def tick(self):
        p = pong(self.last_count)
        self.last_count = ping()
        self.__sample_index = (self.__sample_index + 1) % self.sample_size
        self.sample[self.__sample_index] = p
        return p

    @property
    def rate(self):
        return 1000 / self.mean_elapsed_ms

    @property
    def rate_ms(self):
        return 1 / self.mean_elapsed_ms

    @property
    def mean_elapsed(self):
        return self.sample.sum() / self.sample_size / 1000

    @property
    def mean_elapsed_ms(self):
        return self.sample.sum() / self.sample_size

    @property
    def current_elapsed(self):
        return pong(self.last_count) / 1000

    @property
    def current_elapsed_ms(self):
        return pong(self.last_count)

    @property
    def last_elapsed(self):
        return self.sample[-1] / 1000

    @property
    def last_elapsed_ms(self):
        return self.sample[-1]
