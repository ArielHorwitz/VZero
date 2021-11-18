
import math


class Display:
    @classmethod
    def num(cls, n, sig_digits=4, precision=3, padzero=True, padexp=False,
            force_scientific=False, **kwargs):
        assert sig_digits > 1
        total_length = sig_digits + 5
        fixdecimal = total_length - precision - 1
        assert total_length >= precision+padexp+1
        if n == 0:
            return f'{" "*fixdecimal}0.0{" "*(total_length-fixdecimal-2)}'

        sign = ' '
        pad = "0" if padzero else ""
        xsize = 4 + padexp
        if n < 0:
            sign = '-'
            n *= -1

        e = math.log10(n)
        exponent = int(e-1 if e <= 0 and e != int(e) else e)
        es = f'e-{int(math.fabs(exponent)):0>2}' if exponent < 0 else f'e+{exponent:0>2}'
        fixed_float = n*10**-exponent

        if -(total_length-fixdecimal-precision+1) < exponent < fixdecimal and not force_scientific:
            whole = str(int(n))
            fraction = math.modf(fixed_float/10)[0]
            if exponent < 0:
                fraction = f'{"0"*(-exponent-1)}{str(fraction)[2:]}'
            else:
                fraction = f'{str(fraction)[len(whole)+2:]}'
            w = f'{sign+whole:>{fixdecimal+1}}'
            f = f'{fraction:{pad}<{total_length-fixdecimal-1}}'
            ds = f'{w}.{f}'[:total_length+1] if precision > 0 else f'{str(int(w)):>{total_length+1}}'
            return f'{ds}'

        sig = total_length-padexp-5
        return f'{sign}{round(fixed_float, sig-1):{pad}<{sig+1}}{" " if padexp else ""}{es}'

    @classmethod
    def num_simple(cls, n, rounding=2, pad=12):
        s = f'{round(n, rounding):,}'
        s += '0'*(rounding-len(s.split('.')[-1]))
        return f'{s:>{pad}}'

    @classmethod
    def list(cls, l,
             split=', ', split_line='\n',
             split_threshold=25,
             show_threshold=25,
             pretext='', posttext='',
             value_pad=0, value_cap=float('inf'),
             **kwargs):
        def give_value_str(v):
            return f'{pretext}{cls.s(v, value_cap):<{value_pad}}{posttext}'
        do_split = any(len(str(v)) > split_threshold for v in l)
        if do_split:
            rs = njoin([give_value_str(item) for item in l[:show_threshold]], split=split_line)
        else:
            rs = f'[{split.join(str(item) for item in l[:show_threshold])}]'
        return rs

    @classmethod
    def dict(cls, dictionary: dict, max_depth=float('inf'),
             indent_str='- ', indent_str_end='>',
             key_cap=20, value_cap=float('inf'),
             key_align_right=True, key_guide='', colon=': ',
             split_lists=True, **kwargs):
        def make_indent(indent, ktext='', key_guide=key_guide, key_align_right=key_align_right):
            si = f'{indent_str*indent}{indent_str_end} '
            s = f'{si}{str(ktext):{key_guide}{">" if key_align_right else "<"}{max(0, key_cap - len(si))}}'
            return f'{cls.s(s, key_cap)}'

        def expand_item(item, indent):
            # expand dictionary
            if indent > max_depth:
                r = f'{colon}{cls.s("<MAX CRAWL DEPTH>", value_cap)}'
            elif isinstance(item, dict):
                r = f'{f"{{..}}{nl}" if indent > 0 else nl}{expand_dict(item, indent + 1)}'
                if item == {}:
                    r = f'{{}}'
            # expand list
            elif isinstance(item, list):
                if any((isinstance(v, dict) or isinstance(v, list) or isinstance(v, tuple)) for v in item) or split_lists:
                    r = f'[..]{nl}{expand_list(item, indent + 1)}'
                else:
                    r = f'{colon}{cls.s(str(item), value_cap)}'
            # stringify callable
            elif callable(item):
                name__ = repr(item) if not hasattr(item, "__name__") else item.__name__
                r = f'{colon}<Method:{name__}>'
                if item.__doc__ is not None:
                    # r = f'{colon}<Method:{item.__name__}> {item.__doc__.replace(nl, " | ").replace("  ", "")}'
                    r = f'{colon}{item.__doc__}'
                r = cls.s(r, value_cap)
            # stringify others
            else:
                r = f'{colon}{cls.s(item, value_cap)}'

            return f'{r}'

        def expand_dict(d, indent):
            l = []
            for k, v in d.items():
                if isinstance(v, dict):
                    s = f'{make_indent(indent=indent, ktext="_"*len(indent_str)+f"{k}", key_guide="_")}{expand_item(v, indent)}'
                else:
                    s = f'{make_indent(indent=indent, ktext=k, key_align_right=key_align_right)}{expand_item(v, indent)}'
                l.append(s)
            r = njoin(l)
            return r

        def expand_list(l, indent):
            r = '\n'.join(f'{make_indent(indent=indent)}'
                          f'{expand_item(v, indent)}' for v in l)
            return r

        nl = '\n'
        rs = expand_item(dictionary, -1 if isinstance(dictionary, dict) else 0)
        return rs

    @classmethod
    def num_bar(cls, value, bar_size=5, full_bar_value=1.0,
                        resolution_symbols='‗░▒▓█', overflow_symbol='»',
                        show_number=False,
                        **kwargs):
        # todo fixme showing weird behavior at low values
        # add logarithmic functionality
        remainder = value
        bar = f'{cls.num(round(value, 3))}: ' if show_number else ''
        char_value = full_bar_value / bar_size
        char_resolution = len(resolution_symbols) - 1
        resolution_value = char_value / char_resolution
        for bar_index in range(bar_size):
            r = remainder - char_value
            t = char_value + (r if r < 0 else 0)
            remainder -= t
            if t == 0:
                bar += resolution_symbols[0]
                continue
            resolution_index = int(min(t // resolution_value, char_resolution-1))
            bar += resolution_symbols[resolution_index+1]
        # todo fixme very tiny values show as overflowing... (i assume rounding error)
        # hotfix by ignoring small overflows
        if remainder > resolution_value:
            # bar = bar[:-1] + overflow_symbol
            bar += overflow_symbol
        return bar

    @classmethod
    def s(cls, s, max_length=10000, **kwargs):
        """
        Truncate a display string.

        :param s:           String to truncate and display
        :param max_length:  Maximum characters this string will have
        :return:            New display string
        """
        s = str(s)
        ns = s if max_length == float('inf') else f'{s[:max_length]}'
        if len(s) > len(ns)*2:
            ns = f'{ns[:-3]}...'
        elif len(s) > len(ns):
            ns = f'{ns[:-2]}..'
        return ns

    @classmethod
    def seconds(cls, seconds, pad=False):
            MINUTE, HOUR, DAY, YEAR = 60, 3600, 86400, 31536000
            seconds = int(seconds % 60)
            minutes = int((seconds / MINUTE) % (HOUR / MINUTE))
            hours = int((seconds / HOUR) % (DAY / HOUR))
            days = int((seconds / DAY) % (YEAR / DAY))
            years = int((seconds / YEAR))
            if pad:
                return f'{years:>1} y, {days:>3} d, {hours:0>2}h:{minutes:0>2}m:{seconds:0>2}s'
            else:
                s = []
                if years:
                    s.append(f'{years} y')
                if days:
                    s.append(f'{days} d')
                if seconds or minutes or hours:
                    s.append(f'{hours:0>2}h:{minutes:0>2}m:{seconds:0>2}s')
                if len(s):
                    return njoin(s, split=', ')
                return f'0 s'

    @classmethod
    def auto(cls, v, *args, **kwargs):
        if isinstance(v, int):
            return cls.num(v, *args, **kwargs)
        elif isinstance(v, float):
            return cls.num(v, *args, **kwargs)
        elif isinstance(v, dict):
            return cls.dict(v, *args, **kwargs)
        elif isinstance(v, list) or isinstance(v, tuple) or isinstance(v, set):
            return cls.list(v, *args, **kwargs)
        elif isinstance(v, str):
            return cls.s(v, *args, **kwargs)
        else:
            return v


def njoin(l, split='\n', cap=float('inf'), pretext='', posttext=''):
    return str(split).join(f'{Display.s(f"{pretext}{s}{posttext}", cap)}' for s in l)


def nprint(print_obj, title=None):
    if title is not None:
        print_title(title)
    print(Display.auto(print_obj))


def print_title(title):
    print(make_title(title))


def make_title(
    text, length=75, offset=3, char='_',
    end_line=True, title_gap=True,
    pre_line=True, post_line=False, nonewline=False
    ):
    if title_gap and text!='':
        text = f' {text} '
    if nonewline:
        end_line, pre_line, post_line = False, False, False
    nl = '\n'
    pretext = f'{char*offset}{text}'
    text = f'{pretext:{char}<{length}}'
    prels = '\n' if pre_line else ''
    postls = '\n' if post_line else ''
    return f'{prels}{text}{nl if end_line else ""}{postls}'


def ncoordinates(coords):
    return njoin((Display.auto(_) for _ in coords), split=', ')

adis = Display.auto
