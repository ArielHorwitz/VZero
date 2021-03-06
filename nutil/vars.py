import logging
logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


import collections
import numpy as np
import enum


class PublishSubscribe(collections.defaultdict):
    def __init__(self, name=None):
        super().__init__(lambda: set())
        self.name = name if name is not None else 'Unnamed'

    def subscribe(self, channel, callback):
        assert callable(callback)
        self[channel].add(callback)
        logger.info(f'{callback} subscribed to {channel} channel on {self}')

    def push(self, channels):
        logger.debug(f'{self} pushing channels: {channels}')
        all_callbacks = set()
        for channel in channels:
            all_callbacks.update(self[channel])
        logger.debug(f'{self} collected {len(all_callbacks)} calls: {all_callbacks}')
        for callback in all_callbacks:
            callback()

    def push_all(self):
        self.push(tuple(self.keys()))

    def __repr__(self):
        return f'<{self.name} PublishSubscribe {len(self)} channels {self.total_callbacks} total callbacks>'

    @property
    def total_callbacks(self):
        return sum(len(_) for _ in self.values())


class Interface:
    def __init__(self, name=None):
        if name is None:
            name = 'Unnamed'
        self.name = name
        self.__requests = {}
        self.__queue = []

    def get_flush_queue(self):
        r = self.__queue
        self.__queue = []
        return r

    def append(self, element):
        self.__queue.append(element)

    def register(self, callname, callback):
        if callname in self.__requests:
            logger.warning(f'Request {callname} already registered in {self}. Overwriting... Current requests: {self.requests}')
        self.__requests[callname] = callback

    def request(self, callname, *a, **k):
        if callname not in self.__requests:
            logger.warning(f'No request {callname} registered in {self}. Ignoring {a} {k}... Current requests: {self.requests}')
            return
        return self.__requests[callname](*a, **k)

    @property
    def queue(self):
        return self.__queue

    @property
    def requests(self):
        return list(self.__requests.keys())

    def __repr__(self):
        return f'<Interface: {self.name} ({len(self.__requests)} reqs registered)>'


class FIFO:
    def __init__(self, stack_size):
        self.__stack_index = 0
        self.__stack_size = stack_size
        self.stack = np.zeros(stack_size, dtype=np.float64)

    def reset(self, value=0):
        self.stack[:] = value

    def push(self, value):
        self.__stack_index = (self.__stack_index + 1) % self.__stack_size
        self.stack[self.__stack_index] = value

    @property
    def mean(self):
        return np.sum(self.stack) / self.__stack_size

    @property
    def sum(self):
        return np.sum(self.stack)


class Dict:
    @staticmethod
    def crawl_dict_path(d, path):
        if len(path) == 0:
            return d
        if len(path) == 1:
            try:
                return d[path[0]]
            except:
                return None
        try:
            return crawl_dict_path(d[path[0]], path[1:])
        except:
            return None

    @classmethod
    def _op(cls, d1, d2, op, default=None):
        if default is None:
            default = lambda k: 0
        assert callable(default)
        for k, v in d2.items():
            if k not in d1:
                d1[k] = default(k)
            d1[k] = op(d1[k], d2[k])
        return d1

    @classmethod
    def contains(cls, d1, d2):
        for k, v in d2.items():
            if k not in d1 and v > 0:
                return False
            if d1[k] < v:
                return False
        return True

    @classmethod
    def add(cls, d1, d2, **kwargs):
        return DictOp._op(d1, d2, op=lambda a, b: a+b, **kwargs)

    @classmethod
    def sub(cls, d1, d2, **kwargs):
        return DictOp._op(d1, d2, op=lambda a, b: a-b, **kwargs)

    @classmethod
    def mul(cls, d1, d2, **kwargs):
        return DictOp._op(d1, d2, op=lambda a, b: a*b, **kwargs)

    @classmethod
    def div(cls, d1, d2, **kwargs):
        return DictOp._op(d1, d2, op=lambda a, b: a/b, **kwargs)

    @classmethod
    def sum(cls, d, start=0):
        s = start
        for v in d.values():
            s += v
        return s


class List:
    @staticmethod
    def move_top(l: list, index: int):
        """
        Bump an item to the top of a list in place (without copying).

        :param l:       List
        :param index:   Index int
        :return:        Same list
        """
        item = l.pop(index)
        new_index = 0
        l.insert(new_index, item)
        return new_index

    @staticmethod
    def move_up(l: list, index: int):
        """
        Bump an item up once in a list in place (without copying).

        :param l:       List
        :param index:   Index int
        :return:        Same list
        """
        item = l.pop(index)
        new_index = index - 1 if index > 0 else index
        l.insert(new_index, item)
        return new_index

    @staticmethod
    def move_down(l: list, index: int):
        """
        Bump an item down once in a list in place (without copying).

        :param l:       List
        :param index:   Index int
        :return:        Same list
        """
        item = l.pop(index)
        new_index = index + 1 if index < len(l) else index
        l.insert(new_index, item)
        return new_index

    @staticmethod
    def move_bottom(l: list, index: int):
        """
        Bump an item to the bottom of a list in place (without copying).

        :param l:       List
        :param index:   Index int
        :return:        Same list
        """
        item = l.pop(index)
        new_index = len(l)
        l.insert(new_index, item)
        return new_index

    @staticmethod
    def swap(l: list, index1: int, index2: int):
        """
        Swap the position of two items of a list in place (without copying).

        :param l:       List
        :param index1:  First index
        :param index2:  Second index
        """
        a = l[index1]
        b = l[index2]
        l[index2] = a
        l[index1] = b


class AutoIntEnum(enum.IntEnum):
    def _generate_next_value_(name, start, count, last_values):
        return count


class NP:
    def in_box_mask(points, bl, tr):
        points = np.array(points)
        in_box = np.all(np.logical_and(points >= bl, points <= tr), axis=1)
        return in_box

    def in_box(points, bl, tr):
        return NP.indices(NP.in_box_mask(points, bl, tr))

    def indices(mask):
        return np.asarray(mask).nonzero()[0]

    def argmin(a, mask=None):
        if mask is None:
            return np.array(a).argmin()
        idx = np.flatnonzero(mask)
        out = idx[np.array(a)[idx].argmin()]
        # Or
        # out = np.flatnonzero(mask)[a[mask].argmin()]
        return out


def collide_point(r1, r2, p):
    return collide_points(r1, r2, np.array([p]))

def collide_points(r1, r2, points):
    return np.all(np.logical_and(points >= r1, points < r2), axis=1)

def modify_color(color, v=1, a=1):
    assert 3 <= len(color) <= 4
    if len(color) == 4:
        a = color[3]*a
        color = color[:3]
    return tuple((*(np.array(color)*v), a))

def normalize(a, size=1):
    v_size = np.linalg.norm(a, axis=-1)
    if v_size == 0:
        return np.array(a) * 0
    return np.array(a) * size / v_size

def str2int(s):
    v = 0
    for i, char in enumerate(reversed(s)):
        v += max(ord(char)*(130**i), 130)
    return v

def decimal2hex(n):
    return f"{hex(int(n*255)).split('x')[-1]:0>2}"

def is_floatable(n):
    try:
        float(n)
        return True
    except (ValueError, TypeError):
        return False

def is_intable(n):
    try:
        int(n)
        return True
    except ValueError:
        return False

def try_float(v):
    try:
        return float(v)
    except ValueError:
        return v

def is_iterable(v, count_string=True):
    if not count_string and isinstance(v, str):
        return False
    try:
        v.__iter__()
        return True
    except AttributeError:
        return False

def minmax(minimum, maximum, value):
    assert minimum <= maximum
    if value < minimum:
        return minimum
    elif value > maximum:
        return maximum
    return value

def nsign(n):
    if n > 0:
        return 1
    if n < 0:
        return -1
    return 0

def nsign_str(n):
    if n >= 0:
        return f'+{n}'
    return str(n)


XY = collections.namedtuple('XY', ['x', 'y'])
