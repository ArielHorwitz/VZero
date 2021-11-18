
import random
import hashlib


class Seed:
    """
    A deterministic (seed-based) "random" value generator. Not intended for security at all.
    """
    VERSION = 0.001
    RESOLUTION = 10**15

    def __init__(self, seed=None, resolution=15, last_val=None):
        self.seed = str(random.SystemRandom()) if seed is None else str(seed)
        self.resolution = resolution
        self._last_val = self.seed if last_val is None else last_val

    def randstr(self, str_len=64):
        """
        Returns a string of random characters.

        :param str_len: Length of string to return.
        :return: String
        """
        return str(self._val_gen())[:str_len]

    def randfloat(self, value_range=1, value_range_end=None):
        """
        Returns a random float between 0 and value_range.

        If value_range_end is not provided, the minimum value will be 0 and the maximum value will be value_range. If
        value_range_end is provided, the minimum value will be value_range and the maximum value will be
        value_range_end.

        :param value_range: Maximum value (without value_range_end) or minimum value (with value_range_end)
        :param value_range_end: Maximum value
        :return: Float
        """
        if value_range_end is not None:
            return self.next_val * (value_range_end - value_range) + value_range
        return self.next_val * value_range

    def randint(self, value_range, value_range_end=None):
        # TODO should only accept integer values and should be able to return the maximum value (currently it is
        #  inclusive to the minimum but exclusive to the maximum)
        """
        Returns a random integer.

        If value_range_end is not provided, the minimum value will be 0 and the maximum value will be value_range. If
        value_range_end is provided, the minimum value will be value_range and the maximum value will be
        value_range_end.

        :param value_range: Maximum value (without value_range_end) or minimum value (with value_range_end)
        :param value_range_end: Maximum value
        :return:
        """
        if value_range_end is not None:
            return int(self.next_val * (value_range_end - value_range)) + value_range
        return int(self.next_val * value_range)

    def pop(self, indexable):
        """
        Pops a random item from an indexable.

        :param indexable:   Indexable
        :return:            Popped item from random index
        """
        return indexable.pop(self.randint(len(indexable)))

    def choice(self, iterable):
        """
        Returns a random item from an iterable.

        :param iterable:    Iterable
        :return:            Item from random index
        """
        raw_index = self.randint(len(iterable))
        try:
            return iterable[raw_index]
        except:
            return [*iterable][raw_index]

    def _val_gen(self):
        """
        Hashes the previous value and replaces last value with new one.

        :return: String of hash value
        """
        self._last_val = h256(self._last_val)
        return self._last_val

    def _val_gen_int(self):
        """
        Uses _val_gen() but returns the value as an integer.

        :return: Int
        """
        return int(self._val_gen(), 16)

    def __str__(self):
        return f'<{self.seed}>'

    @property
    def r(self):
        return self.randfloat()

    @property
    def raw_seed(self):
        """
        Returns the original seed as a string.

        :return:    String
        """
        return str(self.seed)

    @property
    def last_val(self):
        """
        Returns the last value as an int.

        :return:    Int
        """
        return self._last_val

    @property
    def next_val(self):
        """
        Returns a number between 0 and 1, with resolution number of digits.

        :return: Float
        """
        return int(self._val_gen_int() % (10**self.resolution)) / (10**self.resolution)


def h256(input_val: str, encode_string=True):
    """
    Create a sha256 digest from a string.

    :param input_val:   String
    :return:            sha256 output of string
    """
    if encode_string:
        input_val = str(input_val).encode()
    return hashlib.sha256(input_val).hexdigest()


SEED = Seed()
