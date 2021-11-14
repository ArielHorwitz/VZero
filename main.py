from pathlib import Path
DEBUG_LOGFILE = Path.cwd()/'data'/'debug.log'

# Logging
import logging
LOG_LEVEL = logging.DEBUG
LOG_LEVEL = logging.INFO
LOG_LEVEL = logging.WARNING

from nutil.file import file_dump
file_dump(DEBUG_LOGFILE, f'Roguesque Debug Log (log level: {LOG_LEVEL})\n\n')

logging.basicConfig(level=LOG_LEVEL, filename=DEBUG_LOGFILE)
logger = logging.getLogger(__name__)
logger.info(f'Logging configured.')


import os
os.environ['KIVY_NO_CONSOLELOG'] = '1'
import kivy


# Run
if __name__ == '__main__':
    print('Debug log file:', DEBUG_LOGFILE)
    from gui.gui import App
    app = App()
    app.run()
