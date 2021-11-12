from pathlib import Path
DEBUG_LOGFILE = Path.cwd()/'debug.log'

from nutil.file import file_dump
file_dump(DEBUG_LOGFILE, 'Roguesque Debug Log\n\n')

# Logging
import logging
logging.basicConfig(level=logging.INFO, filename=DEBUG_LOGFILE)
logger = logging.getLogger(__name__)
logger.info(f'Logging configured.')


import os
os.environ['KIVY_NO_CONSOLELOG'] = '1'
import kivy


# Run
if __name__ == '__main__':
    from gui.gui import App
    print('Debug log file:', DEBUG_LOGFILE)
    app = App()
    app.run()
