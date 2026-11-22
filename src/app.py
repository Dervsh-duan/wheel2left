"""界面：纯 Win32 自绘，深色主题。

设计原则（针对"卡死"这个痛点）：
  - 界面跑在主线程自己的消息循环里，与钩子线程、注入线程完全解耦；
  - 关闭窗口 = 立刻 os._exit，绝不留残留进程；
  - 顶部大开关一键切换，随时能把滚轮还给自己。
"""

import ctypes
import os
import queue
import sys
import tempfile
import threading
import time

from ctypes import wintypes as w

from engine import (
    Engine, MODE_FULLSCREEN, MODE_GLOBAL, MODE_NAMES, MODE_TARGET,
    foreground_process_name,
)
from w32 import (
    DRAWITEMSTRUCT, MSG, PAINTSTRUCT, POINT, RECT, WNDCLASSEXW, WNDPROC,
    dwmapi, gdi32, kernel32, user32,
    BS_OWNERDRAW, DT_CENTER, DT_LEFT, DT_NOPREFIX, DT_SINGLELINE, DT_VCENTER,
    ES_AUTOVSCROLL, ES_MULTILINE, ES_READONLY,
    FW_BOLD, FW_NORMAL, ODS_SELECTED, SW_SHOW, TRANSPARENT,
    WM_CLOSE, WM_COMMAND, WM_CTLCOLOREDIT, WM_CTLCOLORSTATIC, WM_DESTROY,
    WM_DRAWITEM, WM_ERASEBKGND, WM_HOTKEY, WM_PAINT, WM_TIMER,
    WS_CAPTION, WS_CHILD, WS_EX_APPWINDOW, WS_MINIMIZEBOX, WS_OVERLAPPED,
    SW_SHOWNOACTIVATE, WS_SYSMENU, WS_TABSTOP, WS_VISIBLE, WS_VSCROLL,
    make_font, rgb,
)

APP_TITLE = "滚轮 → 左键"
HOTKEY_ID = 1
HOTKEY_MODS = 0x0001 | 0x0002 | 0x0004 | 0x4000   # Ctrl + Alt + Shift + 防重复
HOTKEY_VK = 0x52                                   # R

C_BG = rgb(22, 22, 26)
C_CARD = rgb(32, 32, 39)
C_TEXT = rgb(242, 242, 245)
C_SUB = rgb(138, 138, 152)
C_DIM = rgb(104, 104, 118)
C_ON = rgb(47, 191, 113)
C_ON_DOWN = rgb(38, 168, 96)
C_OFF = rgb(72, 72, 84)
C_OFF_DOWN = rgb(58, 58, 68)
C_ACCENT = rgb(86, 132, 255)
C_LOG_BG = rgb(30, 30, 37)
C_LOG_TEXT = rgb(198, 198, 210)
C_DANGER = rgb(255, 138, 138)

ID_MAIN = 1001
ID_MODE_GLOBAL = 1002
ID_MODE_FS = 1003
ID_QUIT = 1004
ID_RESET = 1005
ID_MODE_TARGET = 1006
ID_LOCK = 1007
ID_LOG = 1100

MODE_BUTTONS = (
    (ID_MODE_GLOBAL, MODE_GLOBAL),
    (ID_MODE_FS, MODE_FULLSCREEN),
    (ID_MODE_TARGET, MODE_TARGET),
)

CW, CH = 520, 640

user32.SetWindowTextW.argtypes = (w.HWND, w.LPCWSTR)
user32.SetWindowTextW.restype = w.BOOL
user32.IsWindowVisible.argtypes = (w.HWND,)
user32.IsWindowVisible.restype = w.BOOL

MAX_LOG_LINES = 120

# 这些进程是系统外壳，不该被当成"游戏"锁进白名单
SKIP_PROCS = {
    "explorer.exe", "applicationframehost.exe", "textinputhost.exe",
    "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
}


def resource_id(value):
    """把整数资源 ID 转成 LPCWSTR 指针（MAKEINTRESOURCE）。"""
    return ctypes.cast(ctypes.c_void_p(value), w.LPCWSTR)


class App:
    def __init__(self):
        self.hwnd = None
        self.engine = None
        self._wp = None
        self._fonts = {}
        self._brushes = {}
        self._controls = {}
        self._log_lines = []
        self._log_lock = threading.Lock()
        self._log_dirty = False
        self._last_sig = None
        self.hotkey_ok = False
        self._closing = False
        self._last_traced_fired = 0
        self._last_trace_time = 0.0

    # ------------------------------------------------------------ 资源
    def font(self, key, size, weight=FW_NORMAL):
        if key not in self._fonts:
            self._fonts[key] = make_font(size, weight)
        return self._fonts[key]

    def brush(self, color):
        if color not in self._brushes:
            self._brushes[color] = gdi32.CreateSolidBrush(color)
        return self._brushes[color]

    # ------------------------------------------------------------ 创建
    def create(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._wp = WNDPROC(self.wnd_proc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wp
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, resource_id(32512))  # IDC_ARROW
        wc.hbrBackground = self.brush(C_BG)
        wc.hIcon = user32.LoadIconW(hinst, resource_id(1))
        wc.hIconSm = wc.hIcon
        wc.lpszClassName = "W2LC_Driver"
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err not in (0, 1410):
                raise RuntimeError(f"注册窗口类失败：{err}")

        style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX
        rc = RECT(0, 0, CW, CH)
        user32.AdjustWindowRectEx(ctypes.byref(rc), style, False, WS_EX_APPWINDOW)
        ww, wh = rc.right - rc.left, rc.bottom - rc.top
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        self.hwnd = user32.CreateWindowExW(
            WS_EX_APPWINDOW, "W2LC_Driver", APP_TITLE, style,
            max(0, (sw - ww) // 2), max(0, (sh - wh) // 2), ww, wh,
            None, None, hinst, None)
        if not self.hwnd:
            raise RuntimeError(f"窗口创建失败：{ctypes.get_last_error()}")

        self.build_children(hinst)
        # 标题栏跟随深色主题（Win10 1809+）
        if dwmapi is not None:
            try:
                v = ctypes.c_int(1)
                dwmapi.DwmSetWindowAttribute(self.hwnd, 20, ctypes.byref(v),
                                             ctypes.sizeof(v))
            except Exception:
                pass
        # 放到右下角，并且不置顶：否则会盖住游戏画面，注入的点击也会落到自己身上
        user32.SetWindowPos(self.hwnd, w.HWND(0),           # HWND_TOP，但不置顶
                            max(0, sw - ww - 24), max(0, sh - wh - 48),
                            0, 0, 0x0001)                     # SWP_NOSIZE
        # 不抢焦点：Chromium / 游戏只在窗口激活时才理会鼠标点击
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.UpdateWindow(self.hwnd)
        r = RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(r))
        self._trace(f"create ok hwnd={self.hwnd} visible={user32.IsWindowVisible(self.hwnd)} "
                    f"rect={r.left},{r.top},{r.right},{r.bottom}")
        # 打包成 --windowed 后没有 stdout，这里不能 print
        return self.hwnd

    def build_children(self, hinst):
        def btn(cid, text, x, y, cw_, ch_):
            h = user32.CreateWindowExW(
                0, "BUTTON", text,
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_OWNERDRAW,
                x, y, cw_, ch_, self.hwnd, w.HMENU(cid), hinst, None)
            self._controls[cid] = h
            return h

        bw = (CW - 48 - 16) // 3
        btn(ID_MAIN, "main", 24, 96, CW - 48, 72)
        for i, (cid, _mode) in enumerate(MODE_BUTTONS):
            btn(cid, "mode", 24 + i * (bw + 8), 206, bw, 38)
        btn(ID_LOCK, "锁定前台程序", CW - 24 - 116, 274, 116, 28)
        btn(ID_RESET, "重置计数", CW - 24 - 84, 362, 84, 24)
        btn(ID_QUIT, "退出程序", CW - 24 - 96, 566, 96, 34)

        self._controls[ID_LOG] = user32.CreateWindowExW(
            0, "EDIT", "",   # 无边框：靠更亮的底色区分区域，避免深色界面上的白描边
            WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
            28, 388, CW - 56, 164, self.hwnd, w.HMENU(ID_LOG), hinst, None)

    # ------------------------------------------------------------ 绘制
    def _fill_round(self, hdc, rc, color, radius, border=None):
        br = gdi32.CreateSolidBrush(color)
        pen = gdi32.CreatePen(0, 1, color if border is None else border)
        ob = gdi32.SelectObject(hdc, br)
        op = gdi32.SelectObject(hdc, pen)
        gdi32.RoundRect(hdc, rc.left, rc.top, rc.right, rc.bottom,
                        radius * 2, radius * 2)
        gdi32.SelectObject(hdc, ob)
        gdi32.SelectObject(hdc, op)
        gdi32.DeleteObject(br)
        gdi32.DeleteObject(pen)

    def _text(self, hdc, text, box, font, color, flags=DT_LEFT | DT_SINGLELINE):
        of = gdi32.SelectObject(hdc, font)
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, color)
        # box 既可能是 (l, t, r, b) 元组，也可能是控件的 RECT
        if isinstance(box, RECT):
            r = RECT(box.left, box.top, box.right, box.bottom)
        else:
            r = RECT(box[0], box[1], box[2], box[3])
        user32.DrawTextW(hdc, text, -1, ctypes.byref(r), flags | DT_NOPREFIX)
        gdi32.SelectObject(hdc, of)

    def draw_button(self, ds):
        hdc = ds.hDC
        rc = ds.rcItem
        cid = ds.CtlID
        pressed = bool(ds.itemState & ODS_SELECTED)
        e = self.engine
        # 先铺满窗口底色，否则圆角外侧会露出控件默认的白底
        user32.FillRect(hdc, ctypes.byref(rc), self.brush(C_BG))

        if cid == ID_MAIN:
            on = bool(e and e.enabled)
            if on:
                color = C_ON_DOWN if pressed else C_ON
            else:
                color = C_OFF_DOWN if pressed else C_OFF
            self._fill_round(hdc, rc, color, 14)
            self._text(hdc, "已开启 · 点击关闭" if on else "已关闭 · 点击开启",
                       (rc.left, rc.top + 14, rc.right, rc.top + 46),
                       self.font("main", 15, FW_BOLD), rgb(255, 255, 255),
                       DT_CENTER | DT_SINGLELINE | DT_VCENTER)
            self._text(hdc, "滚轮 = 鼠标左键" if on else "滚轮已恢复正常",
                       (rc.left, rc.top + 42, rc.right, rc.bottom - 10),
                       self.font("small", 9),
                       rgb(236, 255, 244) if on else C_SUB,
                       DT_CENTER | DT_SINGLELINE | DT_VCENTER)
            return

        if cid in (ID_MODE_GLOBAL, ID_MODE_FS, ID_MODE_TARGET):
            want = {ID_MODE_GLOBAL: MODE_GLOBAL,
                    ID_MODE_FS: MODE_FULLSCREEN,
                    ID_MODE_TARGET: MODE_TARGET}[cid]
            sel = bool(e and e.mode == want)
            if sel:
                bg, bd = C_ACCENT, C_ACCENT
            elif pressed:
                bg, bd = rgb(24, 24, 31), rgb(52, 52, 66)
            else:
                bg, bd = C_CARD, rgb(56, 56, 70)
            self._fill_round(hdc, rc, bg, 10, border=bd)
            self._text(hdc, MODE_NAMES[want], rc,
                       self.font("mode", 9, FW_BOLD if sel else FW_NORMAL),
                       rgb(255, 255, 255) if sel else C_SUB,
                       DT_CENTER | DT_SINGLELINE | DT_VCENTER)
            return

        bg = rgb(24, 24, 31) if pressed else rgb(36, 36, 45)
        self._fill_round(hdc, rc, bg, 8, border=rgb(54, 54, 66))
        if cid == ID_LOCK:
            text, color = "锁定前台程序", C_ACCENT
        elif cid == ID_RESET:
            text, color = "重置计数", C_TEXT
        else:
            text, color = "退出", C_DANGER
        self._text(hdc, text, rc, self.font("small", 9), color,
                   DT_CENTER | DT_SINGLELINE | DT_VCENTER)

    def paint(self):
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(self.hwnd, ctypes.byref(ps))
        rc = RECT(0, 0, CW, CH)
        user32.FillRect(hdc, ctypes.byref(rc), self.brush(C_BG))
        e = self.engine

        self._text(hdc, APP_TITLE, (24, 22, CW - 24, 58),
                   self.font("title", 20, FW_BOLD), C_TEXT)
        self._text(hdc, "让游戏里的滚轮变成鼠标左键", (24, 58, CW - 24, 80),
                   self.font("sub", 9), C_SUB)

        self._text(hdc, "生效范围", (24, 184, CW - 24, 202),
                   self.font("label", 9, FW_BOLD), C_DIM)
        hints = {
            MODE_GLOBAL: "驱动层拦截 · 任何窗口滚轮都等于左键",
            MODE_FULLSCREEN: "驱动层拦截 · 只在前台全屏窗口里转换",
            MODE_TARGET: "驱动层拦截 · 只在锁定的程序里转换，桌面照常滚动",
        }
        self._text(hdc, hints.get(e.mode if e else MODE_TARGET, ""), (24, 250, CW - 24, 270),
                   self.font("hint", 8), C_SUB)

        fg = user32.GetForegroundWindow()
        fg_proc = foreground_process_name()
        if fg and fg != self.hwnd:
            buf = ctypes.create_unicode_buffer(160)
            user32.GetWindowTextW(fg, buf, 160)
            name = buf.value or "（无标题窗口）"
        else:
            name = "（本程序）"

        if e:
            if e.mode == MODE_TARGET and e.targets:
                target = "锁定：" + "、".join(sorted(e.targets))[:32]
                tcolor = C_ON if e.enabled else C_DIM
            elif e.mode == MODE_TARGET:
                target = "未锁定 · 切到游戏滚一下滚轮即自动锁定"
                tcolor = rgb(240, 176, 80)
            else:
                target = "当前程序：" + (fg_proc or "—")
                tcolor = C_DIM
            self._text(hdc, target, (24, 278, CW - 148, 300),
                       self.font("target", 8), tcolor,
                       DT_LEFT | DT_SINGLELINE | DT_VCENTER)

        if e:
            stat = f"已触发 {e.fired} 次"
            if e.dropped:
                stat += f" · 丢弃 {e.dropped}"
            if e.skipped:
                stat += f" · 放行 {e.skipped}"
            self._text(hdc, stat, (24, 306, CW - 130, 328),
                       self.font("stat", 10, FW_BOLD),
                       C_ON if e.enabled else C_SUB)
            if e.last_error:
                self._text(hdc, "!" + e.last_error[:46], (24, 334, CW - 24, 354),
                           self.font("err", 8), rgb(240, 176, 80))
            else:
                self._text(hdc, "前台窗口：" + name[:44], (24, 334, CW - 24, 354),
                           self.font("fgh", 8), C_DIM)

        self._text(hdc, "运行日志", (24, 364, CW - 24, 384),
                   self.font("logt", 8, FW_BOLD), C_DIM)

        tip = ("热键 Ctrl + Alt + Shift + R 随时切换" if self.hotkey_ok
               else "热键被占用，请用上方按钮切换")
        self._text(hdc, tip, (24, 566, CW - 130, 584), self.font("foot", 8), C_SUB)
        self._text(hdc, "关闭窗口即彻底退出", (24, 584, CW - 130, 602),
                   self.font("foot", 8), C_DIM)

        user32.EndPaint(self.hwnd, ctypes.byref(ps))

    # ------------------------------------------------------------ 消息
    def wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == WM_PAINT:
            self.paint()
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_DRAWITEM:
            ds = ctypes.cast(lParam, ctypes.POINTER(DRAWITEMSTRUCT)).contents
            if ds.CtlID in (ID_MAIN, ID_MODE_GLOBAL, ID_MODE_FS, ID_MODE_TARGET,
                            ID_LOCK, ID_RESET, ID_QUIT):
                self.draw_button(ds)
                return 1
            return 0
        if msg == WM_CTLCOLORSTATIC:
            gdi32.SetBkColor(wParam, C_BG)
            gdi32.SetTextColor(wParam, C_TEXT)
            return self.brush(C_BG)
        if msg == WM_CTLCOLOREDIT:
            gdi32.SetBkColor(wParam, C_LOG_BG)
            gdi32.SetTextColor(wParam, C_LOG_TEXT)
            return self.brush(C_LOG_BG)
        if msg == WM_COMMAND:
            self.on_command(wParam & 0xFFFF)
            return 0
        if msg == WM_HOTKEY and wParam == HOTKEY_ID:
            if self.engine:
                self.engine.toggle()
                self.log("热键切换 → " + ("开启" if self.engine.enabled else "关闭"))
                self.refresh(force=True)
            return 0
        if msg == WM_TIMER:
            self.on_timer()
            return 0
        if msg == WM_CLOSE:
            self.shutdown()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    def on_command(self, cid):
        if cid == ID_QUIT:
            self.shutdown()
            return
        if cid == ID_MAIN:
            self.engine.toggle()
            self.log("开启：滚轮现在等于鼠标左键" if self.engine.enabled
                     else "关闭：滚轮已恢复正常")
        elif cid == ID_MODE_GLOBAL:
            self.engine.set_mode(MODE_GLOBAL)
        elif cid == ID_MODE_FS:
            self.engine.set_mode(MODE_FULLSCREEN)
        elif cid == ID_MODE_TARGET:
            self.engine.set_mode(MODE_TARGET)
        elif cid == ID_LOCK:
            self._lock_foreground()
        elif cid == ID_RESET:
            self.engine.reset_counter()
            self.log("计数已重置")
        self.refresh(force=True)

    def _lock_foreground(self):
        """把当前（或最近一个）前台程序加入白名单。"""
        own = ""
        try:
            own = os.path.basename(sys.executable).lower()
        except Exception:
            pass
        name = foreground_process_name()
        if not name or name == own or name in SKIP_PROCS:
            alt = getattr(self.engine, "last_foreground", "")
            if alt and alt != own and alt not in SKIP_PROCS:
                self.log(f"前台是本程序，改用最近记录的程序：{alt}")
                name = alt
            else:
                self.log("没找到可锁定的窗口：先切到游戏，滚一下滚轮，再点「锁定前台程序」")
                return
        self.engine.set_target(name)

    def _remember_foreground(self):
        """定时记住"最近一个不是自己的前台程序"。

        用户点「锁定前台程序」的瞬间，前台一定已经变成本程序了，
        所以必须靠这个缓存来知道"他刚才在玩什么"。
        """
        own = ""
        try:
            own = os.path.basename(sys.executable).lower()
        except Exception:
            pass
        p = foreground_process_name()
        if p and p != own and p not in SKIP_PROCS:
            self.engine.last_foreground = p

    def on_timer(self):
        self._remember_foreground()
        self.drain_logs()
        self.refresh()
        # 计数一变就记一笔到磁盘，方便远程判断"到底拦住没有"
        e = self.engine
        if e and e.fired != self._last_traced_fired:
            now = time.time()
            if now - self._last_trace_time > 3:
                self._last_traced_fired = e.fired
                self._last_trace_time = now
                self._trace(f"fired={e.fired} dropped={e.dropped} skipped={e.skipped}")

    def refresh(self, force=False):
        """只在状态真的变化时重绘，避免闪烁和空转。"""
        e = self.engine
        fg = foreground_process_name() if e.mode == MODE_TARGET else ""
        sig = (e.enabled, e.mode, tuple(sorted(e.targets)), e.fired,
               e.dropped, e.last_error, self.hotkey_ok, fg)
        if not force and sig == self._last_sig:
            return
        self._last_sig = sig
        user32.InvalidateRect(self.hwnd, None, False)
        for cid, h in self._controls.items():
            if cid != ID_LOG:
                user32.InvalidateRect(h, None, True)

    # ------------------------------------------------------------ 日志
    def log(self, text):
        """线程安全，任何线程都能调用。"""
        line = f"{time.strftime('%H:%M:%S')}  {text}"
        with self._log_lock:
            self._log_lines.append(line)
            if len(self._log_lines) > MAX_LOG_LINES:
                del self._log_lines[:len(self._log_lines) - MAX_LOG_LINES]
            self._log_dirty = True

    def drain_logs(self):
        with self._log_lock:
            if not self._log_dirty:
                return
            self._log_dirty = False
            text = "\r\n".join(self._log_lines)
        h = self._controls.get(ID_LOG)
        if h:
            user32.SetWindowTextW(h, text)
            # 让日志自动停在最新一行
            user32.SendMessageW(h, 0x00B1, 0x7FFFFFFF, 0x7FFFFFFF)  # EM_SETSEL
            user32.SendMessageW(h, 0x00B7, 0, 0)                    # EM_SCROLLCARET

    # ------------------------------------------------------------ 退出
    def _trace(self, msg):
        try:
            path = os.path.join(tempfile.gettempdir(), "Wheel2LeftDriver.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        except Exception:
            pass
    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        fired = self.engine.fired if self.engine else -1
        self._trace(f"shutdown 开始 fired={fired}")
        try:
            if self.engine:
                self.engine.enabled = False   # 立刻停止转换，别在退出途中还吞滚轮
        except Exception:
            pass
        # 兜底：正常退出若被卡住的线程拖住，3 秒后强杀
        threading.Thread(target=self._exit_watchdog, daemon=True).start()
        # 正常路径：销毁窗口 → WM_DESTROY → PostQuitMessage → 消息循环结束 → 进程收尾
        user32.DestroyWindow(self.hwnd)

    def _exit_watchdog(self):
        time.sleep(3.0)
        self._trace("兜底：强制退出")
        try:
            kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 0)
        except Exception:
            pass
        os._exit(0)

    # ------------------------------------------------------------ 运行
    def run(self):
        self.engine = Engine(on_log=self.log, on_state=lambda: self.refresh())
        try:
            self.engine.start()
        except Exception as e:
            self._trace(f"engine.start 失败: {type(e).__name__}: {e}")
            user32.MessageBoxW(
                None,
                "启动失败：拦截驱动没有就绪。\n\n"
                f"{e}\n\n"
                "解决办法：\n"
                "1. 先运行压缩包里的「安装驱动（右键管理员运行）.bat」；\n"
                "2. 然后右键本程序 → 以管理员身份运行。",
                APP_TITLE, 0x10)
            return 1

        self.hotkey_ok = bool(user32.RegisterHotKey(
            self.hwnd, HOTKEY_ID, HOTKEY_MODS, HOTKEY_VK))
        self.engine.own_hwnd = self.hwnd
        ok, info = self.engine.self_test()
        if ok:
            self.log("拦截驱动已连接")
        else:
            self.log("拦截驱动异常：" + info[:60])
        user32.SetTimer(self.hwnd, 1, 300, None)
        self.log("已启动 · 范围：" + MODE_NAMES.get(self.engine.mode, ""))
        self._trace(f"启动完成 driver={self.engine.driver_ok} devices={self.engine.mouse_devices}")
        if self.hotkey_ok:
            self.log("热键：Ctrl + Alt + Shift + R")
        else:
            self.log("热键被其他程序占用，请用界面按钮切换")

        msg = MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                self._trace(f"消息循环退出 ret={ret} err={ctypes.get_last_error()}")
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        try:
            self.engine.stop()
        except Exception:
            pass
        return 0


def main():
    app = App()
    try:
        app.create()
    except Exception as e:
        user32.MessageBoxW(None, f"启动失败：{e}", APP_TITLE, 0x10)
        return 1
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
