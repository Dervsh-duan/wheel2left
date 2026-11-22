"""入口：单实例检查 + 启动界面。"""

import ctypes
import os
import sys

from ctypes import wintypes as w

# 打包成 --windowed 后没有控制台，sys.stdout 是 None。
# 任何一句 print 都会抛 AttributeError 把启动流程打断，这里先兜住。
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from w32 import user32

CLASS_NAME = "W2LC_Driver"

TRACE = os.path.join(os.environ.get("TEMP", "."), "Wheel2LeftDriver.log")


def _trace(msg):
    try:
        import time
        with open(TRACE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} [main] {msg}\n")
    except Exception:
        pass


def _hook_exc(exc_type, exc, tb):
    import traceback
    _trace("未捕获异常: " + "".join(traceback.format_exception(exc_type, exc, tb)).replace("\n", " | "))


sys.excepthook = _hook_exc

user32.FindWindowW.argtypes = (w.LPCWSTR, w.LPCWSTR)
user32.FindWindowW.restype = w.HWND
user32.IsWindowVisible.argtypes = (w.HWND,)
user32.IsWindowVisible.restype = w.BOOL
user32.PostMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
user32.PostMessageW.restype = w.BOOL


def already_running():
    """用窗口类名判断有没有旧实例。比 mutex 靠谱：进程死了 mutex 可能残留。"""
    h = user32.FindWindowW(CLASS_NAME, None)
    if not h:
        return False
    # 窗口存在但已经不响应，说明是僵尸，直接关掉再来
    if not user32.IsWindowVisible(h):
        return False
    ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    return True


def main():
    if already_running():
        user32.MessageBoxW(
            None, "程序已经在运行了。\n\n如果要重新开始，请先关掉右下角的旧窗口。",
            "滚轮 → 左键", 0x40)
        return 0

    from app import App
    app = App()
    try:
        app.create()
    except Exception as e:
        app._trace(f"create 失败: {type(e).__name__}: {e}")
        user32.MessageBoxW(None, f"启动失败：{e}", "滚轮 → 左键", 0x10)
        return 1
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
