
import os
import sys
import traceback
import copy

from nutil.display import make_title, adis


def format_exc(e):
    """
    Return a formatted string of an exception traceback.

    :param e:       Exception
    :return:        Formatted multi-line string
    """
    strs = []
    for line in traceback.format_exception(*sys.exc_info()):
        strs.append(str(line))
    return ''.join(strs)

def fdebug(func):
    @functools.wraps(func)
    def wrapper_debug(*args, **kwargs):
        print('\n'.join([
            make_title(f'Calling {func.__name__} ({func})', length=150),
            f'Args: {adis(args)}',
            f'Kwargs: {adis(kwargs)}',
            ]))
        return_value = func(*args, **kwargs)
        print('\n'.join([
            make_title(f'{func.__name__} ({func}) returned:', length=150),
            f'{return_value}',
            ]))
        return return_value
    return wrapper_debug

def vdebug(var, name='Variable', print_=True):
    r = '\n'.join([
        make_title(f'{name} Debug'),
        f'ID: {id(var)}',
        f'Type: {type(var)}',
        f'Repr: {repr(var)}',
        f'Str: {str(var)}',
        f'Value: {var}',
        f'Formatted:\n{adis(var)}',
        ])
    if print_:
        print(r)
    return r

def clear_console():
    """
    A common function, is difficult to write.
    """
    if os.name == 'posix':
        os.system('clear')
    elif os.name == 'nt':
        os.system('cls')

def attrs_summary(o):
    return '\n'.join(f'{_:.<20}: {getattr(o, _)}' for _ in filter(
        lambda k: not k.startswith('_'), o.__dict__.keys()))
