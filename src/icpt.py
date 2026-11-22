"""Interception 驱动库的 ctypes 封装。

为什么用驱动：游戏（尤其全屏独占）只认硬件层事件，Windows 用 SendInput /
PostMessage 模拟出来的点击会被标记成"注入"，直接被过滤掉。Interception 是
一个内核级鼠标/键盘过滤驱动，在这一层拦下滚轮、再在这一层发左键，游戏看到
的就是真实硬件动作，无法区分。
"""

import ctypes
import os
import sys
from ctypes import wintypes as w

# ---------------------------------------------------------------- 设备编号
INTERCEPTION_MAX_KEYBOARD = 10
INTERCEPTION_MAX_MOUSE = 10


def INTERCEPTION_KEYBOARD(index):
    return index + 1


def INTERCEPTION_MOUSE(index):
    return INTERCEPTION_MAX_KEYBOARD + index + 1


# ---------------------------------------------------------------- 鼠标 state
MOUSE_LEFT_BUTTON_DOWN = 0x001
MOUSE_LEFT_BUTTON_UP = 0x002
MOUSE_RIGHT_BUTTON_DOWN = 0x004
MOUSE_RIGHT_BUTTON_UP = 0x008
MOUSE_MIDDLE_BUTTON_DOWN = 0x010
MOUSE_MIDDLE_BUTTON_UP = 0x020
MOUSE_BUTTON_4_DOWN = 0x040
MOUSE_BUTTON_4_UP = 0x080
MOUSE_BUTTON_5_DOWN = 0x100
MOUSE_BUTTON_5_UP = 0x200
MOUSE_WHEEL = 0x400
MOUSE_HWHEEL = 0x800

FILTER_MOUSE_NONE = 0x0000
FILTER_MOUSE_ALL = 0xFFFF
FILTER_MOUSE_WHEEL = MOUSE_WHEEL
FILTER_MOUSE_HWHEEL = MOUSE_HWHEEL


class MouseStroke(ctypes.Structure):
    """对应 C 的 InterceptionMouseStroke（20 字节，注意 state 在前、flags 在后）。"""

    _fields_ = [
        ("state", ctypes.c_ushort),
        ("flags", ctypes.c_ushort),
        ("rolling", ctypes.c_short),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("information", ctypes.c_uint),
    ]


# InterceptionStroke 在头文件里是 char[sizeof(InterceptionMouseStroke)]，
# 直接用等长结构体最省事。
Stroke = MouseStroke

PREDICATE = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)


def dll_candidates():
    """按优先级列出 interception.dll 可能出现的位置。"""
    here = os.path.dirname(os.path.abspath(__file__))
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
        roots.append(os.path.dirname(sys.executable))
    roots.append(os.path.abspath(os.path.join(here, "..")))
    roots.append(here)
    out = []
    for r in roots:
        for sub in ("", "driver", os.path.join("driver", "Interception", "library", "x64")):
            out.append(os.path.join(r, sub, "interception.dll"))
    out.append("interception.dll")
    return out


class Interception:
    """一个最小可用的封装：只暴露本项目要用的接口。"""

    def __init__(self):
        self._dll = None
        self._path = None
        self._predicate = None   # 必须持引用，否则会被 GC 掉导致回调崩溃

    # ------------------------------------------------------------ 加载
    def load(self):
        if self._dll is not None:
            return True
        errors = []
        for p in dll_candidates():
            if p != "interception.dll" and not os.path.exists(p):
                continue
            try:
                dll = ctypes.WinDLL(p)
            except OSError as e:
                errors.append(f"{p}: {e}")
                continue
            self._bind(dll)
            self._dll = dll
            self._path = p
            return True
        raise RuntimeError("找不到 interception.dll\n" + "\n".join(errors[-3:]))

    def _bind(self, dll):
        dll.interception_create_context.argtypes = []
        dll.interception_create_context.restype = ctypes.c_void_p
        dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
        dll.interception_destroy_context.restype = None
        dll.interception_set_filter.argtypes = [ctypes.c_void_p, PREDICATE, ctypes.c_ushort]
        dll.interception_set_filter.restype = None
        dll.interception_wait.argtypes = [ctypes.c_void_p]
        dll.interception_wait.restype = ctypes.c_int
        dll.interception_wait_with_timeout.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        dll.interception_wait_with_timeout.restype = ctypes.c_int
        dll.interception_receive.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(MouseStroke), ctypes.c_uint]
        dll.interception_receive.restype = ctypes.c_int
        dll.interception_send.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(MouseStroke), ctypes.c_uint]
        dll.interception_send.restype = ctypes.c_int
        dll.interception_is_mouse.argtypes = [ctypes.c_int]
        dll.interception_is_mouse.restype = ctypes.c_int
        dll.interception_is_keyboard.argtypes = [ctypes.c_int]
        dll.interception_is_keyboard.restype = ctypes.c_int
        dll.interception_is_invalid.argtypes = [ctypes.c_int]
        dll.interception_is_invalid.restype = ctypes.c_int
        dll.interception_get_hardware_id.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        dll.interception_get_hardware_id.restype = ctypes.c_uint

    # ------------------------------------------------------------ 上下文
    def create_context(self):
        if self._dll is None:
            self.load()
        ctx = self._dll.interception_create_context()
        if not ctx:
            raise RuntimeError(
                "无法打开拦截驱动。\n\n"
                "通常是下面两个原因：\n"
                "1) 驱动还没安装 —— 运行一次“安装驱动”里的脚本；\n"
                "2) 程序没有以管理员身份运行。")
        return ctx

    def destroy_context(self, ctx):
        if self._dll and ctx:
            self._dll.interception_destroy_context(ctx)

    def filter_mouse(self, ctx, mask):
        """只把 mask 里的事件交给本程序，其它事件驱动直接放行。"""
        if self._predicate is None:
            self._predicate = PREDICATE(lambda dev: 1 if self._dll.interception_is_mouse(dev) else 0)
        self._dll.interception_set_filter(ctx, self._predicate, mask)

    def wait(self, ctx, timeout_ms):
        return self._dll.interception_wait_with_timeout(ctx, timeout_ms)

    def receive(self, ctx, dev, stroke):
        return self._dll.interception_receive(ctx, dev, ctypes.byref(stroke), 1)

    def send(self, ctx, dev, stroke):
        return self._dll.interception_send(ctx, dev, ctypes.byref(stroke), 1)

    def is_mouse(self, dev):
        return bool(self._dll.interception_is_mouse(dev))

    def is_keyboard(self, dev):
        return bool(self._dll.interception_is_keyboard(dev))

    def is_invalid(self, dev):
        return bool(self._dll.interception_is_invalid(dev))

    def hardware_id(self, ctx, dev):
        buf = ctypes.create_unicode_buffer(512)
        n = self._dll.interception_get_hardware_id(
            ctx, dev, ctypes.cast(buf, ctypes.c_void_p), ctypes.sizeof(buf))
        return buf.value if n else ""

    @property
    def path(self):
        return self._path


def make_stroke(state=0, flags=0, rolling=0, x=0, y=0):
    s = MouseStroke()
    s.state = state
    s.flags = flags
    s.rolling = rolling
    s.x = x
    s.y = y
    # information 保持 0：不要留任何可被游戏识别的自定义标记
    s.information = 0
    return s
