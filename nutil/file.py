
import pathlib
import os
import shutil
import platform
import subprocess
import datetime


def get_path(path=None, file=None, from_home=False):
    """
    Get a pathlib Path originating from user home directory.

    :param path: list[str]
        List of directories in path.
    :param file: str
        File name.
    :return: pathlib.Path
    """
    final_path = pathlib.Path.home() if from_home else path.pop(0)
    if not final_path.is_dir():
        final_path.mkdir()

    # interpret path as a list of dir names
    if isinstance(path, list):
        for directory in path:
            final_path = final_path / directory
            if not final_path.is_dir():
                final_path.mkdir()
    # interpret path as a dir name
    elif isinstance(path, str):
        final_path = final_path / path
        if not final_path.is_dir():
            final_path.mkdir()
    else:
        raise ValueError(f'path must be string (dir name) or list of strings (dir name path)')

    if file is not None:
        final_path = final_path / file
    return final_path

def give_usr_dir(dir_name):
    """
    Give a directory path in the user's local home directory according to the OS (NT or posix)

    :param dir_name:    Directory name
    :return:            Path to directory (pathlib.Path)
    """
    path = pathlib.Path.home()
    if os.name == 'posix':
        path = path / '.local' / 'share' / f'{dir_name.lower()}'
    elif os.name == 'nt':
        path = path / 'AppData' / 'Local' / f'{dir_name.capitalize()}'
    else:
        raise NotImplementedError(f'Unknown OS ({os.name})')
    if not path.is_dir():
        path.mkdir()
    return path

def file_dump(file, d, clear=True):
    with open(file, 'w' if clear else 'a') as f:
        f.write(d)

def file_load(file):
    with open(file, 'r') as f:
        d = f.read()
    return d

def file_copy(src, dst, *a, **k):
    return shutil.copy(src, dst, *a, **k)

def log_disk(log_path, message, clear=False, timestamp=False, force_print=False):
    """
    Log a message to file on disk.

    :param log_path:        Path of file to append message
    :param message:         Message string to append to file
    :param clear:           Clear the file before writing
    :param timestamp:       Add a timestamp to the message
    :param force_print:     Print message to console
    """
    if force_print:
        print(message)
    times = f'{log_timestamp()} - ' if timestamp else ''
    with open(log_path, 'w' if clear else 'a') as f:
        f.write(f'{times}{message}\n')

def log_timestamp():
    """
    Return a string-sortable timestamp.

    :return:    Formatted timestamp
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def open_file_explorer(path):
    if platform.system() == 'Windows':
        os.startfile(path)
    elif platform.system() == 'Darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])
