import logging
logger = logging.getLogger(__name__)
LOG_LEVELS = (logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)
LOG_LEVEL = LOG_LEVELS[3]


from pathlib import Path
import time
import os
from nutil.file import file_dump, file_load, file_copy
from nutil.debug import format_exc

INDIVIDUAL_CRASH_LOG = False
LAUNCH_TIME = int(time.time())
LOG_DIR = Path.cwd() / 'logs'
DEBUG_LOGFILE = LOG_DIR / 'debug.log'
CRASH_LOGFILE = LOG_DIR / f'crash-{LAUNCH_TIME}.log'
CRASH_CANARY = Path.cwd() / '.crashing'
if not LOG_DIR.is_dir():
    LOG_DIR.mkdir()


def configure_logging():
    file_dump(DEBUG_LOGFILE, f'Debug Log (log level: {LOG_LEVEL}) - {LAUNCH_TIME}\n\n')
    logging.basicConfig(level=LOG_LEVEL, filename=DEBUG_LOGFILE)
    os.environ['KIVY_NO_CONSOLELOG'] = '1'  # Prevent kivy console output
    logger.info(f'Logging configured.')


def run_app():
    try:
        from gui.gui import App
        App().run()
        logger.info(f'App closed, wrapping up...')
        if CRASH_CANARY.is_file():
            crash_data = file_load(CRASH_CANARY)
            CRASH_CANARY.unlink()
            raise RuntimeError(f'Found crash canary file:\n\n{crash_data}')
    except Exception as e:
        logger.info(format_exc(e))
        if INDIVIDUAL_CRASH_LOG:
            if DEBUG_LOGFILE.is_file():
                file_copy(DEBUG_LOGFILE, CRASH_LOGFILE)
            else:
                file_dump(CRASH_LOGFILE, f'Missing original log file!\n{format_exc(e)}')
    if INDIVIDUAL_CRASH_LOG:
        DEBUG_LOGFILE.unlink()


def main():
    configure_logging()
    run_app()


# Run
if __name__ == '__main__':
    main()
