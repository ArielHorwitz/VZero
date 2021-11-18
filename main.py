from pathlib import Path
DEBUG_LOGFILE = Path.cwd()/'data'/'debug.log'


import logging
logger = logging.getLogger(__name__)
# I am so lazy I can't bother to retype the default log level,
#   so I choose an index.
LOG_LEVELS = (logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)
LOG_LEVEL = LOG_LEVELS[3]


def configure_logging():
    from nutil.file import file_dump
    file_dump(DEBUG_LOGFILE, f'Roguesque Debug Log (log level: {LOG_LEVEL})\n\n')
    logging.basicConfig(level=LOG_LEVEL, filename=DEBUG_LOGFILE)

    # Prevent kivy console output
    import os
    os.environ['KIVY_NO_CONSOLELOG'] = '1'
    logger.info(f'Logging configured.')


def say_hello():
    from data import TITLE
    launch = f'Launching {TITLE}'
    logger.info(launch)
    print(launch)
    print('Debug log file:', DEBUG_LOGFILE)


def main():
    configure_logging()
    say_hello()
    from gui.gui import App
    App().run()


# Run
if __name__ == '__main__':
    main()
