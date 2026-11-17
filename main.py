import ctypes
import sys
import traceback

from fighter.ui import GameApp

if __name__ == "__main__":
    try:
        GameApp().run()
    except Exception:
        tb = traceback.format_exc()
        try:
            ctypes.windll.user32.MessageBoxW(0, tb, "LAN Fighter 启动失败", 0x10)
        except Exception:
            pass
        sys.exit(1)
 