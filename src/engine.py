"""驱动级引擎：在内核驱动层把滚轮换成左键。

和上一版（用户层钩子 + SendInput）的本质区别：
  - 上一版：先让系统把滚轮事件算完，再"补发"一个左键。补发的事件带注入标记，
    全屏游戏（RawInput / DirectInput）会直接丢掉，所以在游戏里永远无效。
  - 这一版：在驱动层就把滚轮截住，一个字节都不往系统送；左键也从驱动层发出，
    对游戏来说和真人按左键完全一样。

线程模型：只用一个工作线程。因为只过滤"滚轮"这一种事件，流量极小，用不着
多线程；单线程反而免去了驱动上下文的并发问题，也更容易在异常时干净退出。
"""

import ctypes
import os
import threading
import time

from ctypes import wintypes as w

import config
import icpt
from icpt import (
    FILTER_MOUSE_WHEEL, MOUSE_HWHEEL, MOUSE_LEFT_BUTTON_DOWN,
    MOUSE_LEFT_BUTTON_UP, MOUSE_WHEEL, Interception, MouseStroke,
)
from w32 import RECT, kernel32, user32

MODE_GLOBAL = "global"          # 任何地方滚轮都等于左键
MODE_FULLSCREEN = "fullscreen"  # 只在全屏窗口里转换，桌面照常滚动
MODE_TARGET = "target"          # 只在锁定的 exe 里转换（默认）

MODE_NAMES = {
    MODE_GLOBAL: "全部窗口",
    MODE_FULLSCREEN: "仅全屏",
    MODE_TARGET: "指定程序",
}

CLICK_HOLD_MS = 12              # 左键按下到抬起，太短部分引擎会当成没按
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_DESKTOP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def process_name_of(hwnd):
    """窗口所属进程的 exe 文件名（小写）。取不到返回空串。

    用 QueryFullProcessImageName 而不是 GetModuleFileNameEx：前者只需要
    PROCESS_QUERY_LIMITED_INFORMATION 权限，对普通权限的其他进程也能读。
    """
    if not hwnd:
        return ""
    pid = w.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = w.DWORD(1024)
        if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)


def foreground_process_name():
    return process_name_of(user32.GetForegroundWindow())


def ensure_driver_service(name="mouse"):
    """确保过滤驱动服务在跑。开机后 PnP 一般会自动拉起，这里只是兜底。

    失败不抛异常：真正能不能用，由 create_context 说了算。
    """
    try:
        adv = ctypes.WinDLL("advapi32", use_last_error=True)
        adv.OpenSCManagerW.argtypes = (w.LPCWSTR, w.LPCWSTR, w.DWORD)
        adv.OpenSCManagerW.restype = w.HANDLE
        adv.OpenServiceW.argtypes = (w.HANDLE, w.LPCWSTR, w.DWORD)
        adv.OpenServiceW.restype = w.HANDLE
        adv.StartServiceW.argtypes = (w.HANDLE, w.DWORD, ctypes.POINTER(w.LPCWSTR))
        adv.StartServiceW.restype = w.BOOL
        adv.CloseServiceHandle.argtypes = (w.HANDLE,)
        adv.CloseServiceHandle.restype = w.BOOL

        scm = adv.OpenSCManagerW(None, None, 0x0001)  # SC_MANAGER_CONNECT
        if not scm:
            return False
        try:
            svc = adv.OpenServiceW(scm, name, 0x0010 | 0x0004)  # START | QUERY_STATUS
            if not svc:
                return False
            try:
                adv.StartServiceW(svc, 0, None)   # 已在运行会返回 1056，忽略
                return True
            finally:
                adv.CloseServiceHandle(svc)
        finally:
            adv.CloseServiceHandle(scm)
    except Exception:
        return False


def foreground_is_fullscreen():
    """前台窗口是否铺满整个主屏（全屏独占 / 无边框全屏都算）。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buf, 64)
    if buf.value in _DESKTOP_CLASSES:
        return False
    rc = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
        return False
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    return rc.left <= 1 and rc.top <= 1 and rc.right >= sw - 1 and rc.bottom >= sh - 1


def foreground_title(limit=44):
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(200)
    user32.GetWindowTextW(hwnd, buf, 200)
    return buf.value[:limit]


class Engine:
    def __init__(self, on_log=None, on_state=None):
        self.on_log = on_log or (lambda msg: None)
        self.on_state = on_state or (lambda: None)

        self.enabled = True
        self.mode, self.targets = config.load()
        self.fired = 0          # 成功转换的滚轮次数
        self.dropped = 0        # 发送失败的次数
        self.skipped = 0        # 策略决定放行（滚轮照常滚动）的次数
        self.last_error = ""
        self.own_hwnd = None
        self.driver_ok = False
        self.mouse_devices = 0
        self.last_foreground = ""   # 最近看到的非自身前台进程，给界面显示

        self._icpt = Interception()
        self._ctx = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._proc_cache = {}       # hwnd -> (时间戳, exe 名)，避免每次都开进程

    # ------------------------------------------------------------ 生命周期
    def start(self):
        ensure_driver_service("mouse")
        self._icpt.load()
        try:
            self._ctx = self._icpt.create_context()
        except RuntimeError as e:
            self.last_error = "驱动未就绪"
            raise RuntimeError(str(e))

        # 只接管滚轮，其它鼠标事件驱动直接放行 —— 万一本程序异常，
        # 移动和点击仍然正常，最坏情况也只是滚轮暂时不动。
        self._icpt.filter_mouse(self._ctx, FILTER_MOUSE_WHEEL)
        self.driver_ok = True

        self._running = True
        self._thread = threading.Thread(target=self._loop, name="interception", daemon=True)
        self._thread.start()

        # 数一下有几个鼠标设备，写进日志方便排查
        try:
            devs = []
            for i in range(icpt.INTERCEPTION_MAX_MOUSE):
                dev = icpt.INTERCEPTION_MOUSE(i)
                if not self._icpt.is_invalid(dev):
                    devs.append(dev)
            self.mouse_devices = len(devs)
        except Exception:
            pass

        self.on_log(f"驱动已接管滚轮 · 范围：{MODE_NAMES.get(self.mode, self.mode)}")
        if self.mode == MODE_TARGET:
            if self.targets:
                self.on_log("目标程序：" + "、".join(sorted(self.targets)))
            else:
                self.on_log("还没锁定程序：切到游戏窗口滚一下滚轮就会自动锁定")
        if self.mouse_devices:
            self.on_log(f"发现 {self.mouse_devices} 个鼠标设备")
        return True

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._ctx:
            try:
                self._icpt.destroy_context(self._ctx)
            except Exception:
                pass
            self._ctx = None
        self.driver_ok = False

    # ------------------------------------------------------------ 工作线程
    def _loop(self):
        ic = self._icpt
        ctx = self._ctx
        while self._running:
            try:
                dev = ic.wait(ctx, 80)
                if not dev or ic.is_invalid(dev):
                    continue
                if not ic.is_mouse(dev):
                    continue

                stroke = MouseStroke()
                if ic.receive(ctx, dev, stroke) != 1:
                    continue

                is_wheel = bool(stroke.state & (MOUSE_WHEEL | MOUSE_HWHEEL))
                if is_wheel and self._should_convert():
                    self._emit_click(ctx, dev)
                    continue          # 滚轮被吞掉，不再往系统送

                if is_wheel:
                    self.skipped += 1
                # 放行：把原事件原样还给系统
                ic.send(ctx, dev, stroke)
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
                self.on_log("拦截线程异常：" + self.last_error)
                time.sleep(0.05)

    def _cached_process_name(self, hwnd):
        now = time.time()
        hit = self._proc_cache.get(hwnd)
        if hit and now - hit[0] < 0.5:
            return hit[1]
        name = process_name_of(hwnd)
        if len(self._proc_cache) > 64:
            self._proc_cache.clear()
        self._proc_cache[hwnd] = (now, name)
        return name

    def _should_convert(self):
        if not self.enabled:
            return False

        hwnd = user32.GetForegroundWindow()
        # 无论什么模式都记一下最近的前台程序，界面「锁定」按钮要用
        if hwnd and hwnd != self.own_hwnd:
            seen = self._cached_process_name(hwnd)
            if seen:
                self.last_foreground = seen

        if self.mode == MODE_GLOBAL:
            return True
        # 前台是本程序 / 桌面 / 任务栏时不动，否则会点到自己界面
        if not hwnd or hwnd == self.own_hwnd:
            return False
        if self.mode == MODE_FULLSCREEN:
            return foreground_is_fullscreen()

        # MODE_TARGET：只认锁定过的 exe
        name = self._cached_process_name(hwnd)
        if not name:
            return False
        if name in self.targets:
            return True
        # 还没锁定任何程序时，在全屏窗口里滚第一下就自动锁定。
        # 这样开箱即用，又不会把桌面上的误滚变成点击。
        if not self.targets and foreground_is_fullscreen():
            self.targets.add(name)
            config.save(self.mode, self.targets)
            self.on_log(f"已自动锁定「{name}」，滚轮只在这个程序里生效")
            self.on_state()
            return True
        return False

    def set_target(self, name):
        """把某个 exe 加入白名单并切到「指定程序」模式。"""
        name = (name or "").strip().lower()
        if not name:
            return False
        self.targets.add(name)
        self.mode = MODE_TARGET
        config.save(self.mode, self.targets)
        self.on_log(f"已锁定「{name}」，只有它的滚轮会变成左键")
        self.on_state()
        return True

    def clear_targets(self):
        self.targets.clear()
        config.save(self.mode, self.targets)
        self.on_log("已清空目标程序，切到目标程序后滚一下滚轮即可重新锁定")
        self.on_state()

    def _emit_click(self, ctx, dev):
        down = icpt.make_stroke(state=MOUSE_LEFT_BUTTON_DOWN)
        up = icpt.make_stroke(state=MOUSE_LEFT_BUTTON_UP)
        n1 = self._icpt.send(ctx, dev, down)
        time.sleep(CLICK_HOLD_MS / 1000.0)
        n2 = self._icpt.send(ctx, dev, up)
        if n1 == 1 and n2 == 1:
            self.fired += 1
        else:
            self.dropped += 1
            self.last_error = "左键发送被驱动拒绝"

    # ------------------------------------------------------------ 对外接口
    def toggle(self):
        self.enabled = not self.enabled
        self.on_log("开启：滚轮现在等于鼠标左键" if self.enabled else "关闭：滚轮已恢复正常")
        self.on_state()

    def set_mode(self, mode):
        if mode == self.mode:
            return
        if mode not in MODE_NAMES:
            return
        self.mode = mode
        config.save(self.mode, self.targets)
        label = MODE_NAMES[mode]
        if mode == MODE_TARGET and not self.targets:
            self.on_log(f"范围：{label} · 切到游戏里滚一下滚轮即可自动锁定")
        else:
            self.on_log(f"范围：{label}")
        self.on_state()

    def reset_counter(self):
        self.fired = 0
        self.dropped = 0
        self.skipped = 0

    def self_test(self):
        """给界面用：确认驱动可用并返回一句人话。"""
        try:
            self._icpt.load()
        except Exception as e:
            self.last_error = str(e)
            return False, self.last_error
        return True, f"驱动库：{self._icpt.path}"
