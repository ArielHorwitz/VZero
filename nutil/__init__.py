import os, sys

def restart_script():
    """
    A common function, is difficult to write.
    """
    os.execl(sys.executable, sys.executable, *sys.argv)
