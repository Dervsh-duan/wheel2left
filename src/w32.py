"""Win32 API 绑定与结构体定义（纯 ctypes，无第三方依赖）。"""

import ctypes
from ctypes import wintypes as w

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
try:
    dwmapi = ctypes.WinDLL("dwmapi")
except OSError:
    dwmapi = None

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, w.WPARAM, w.LPARAM)

# ---------------------------------------------------------------- 消息
WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_DRAWITEM = 0x002B
WM_CTLCOLORSTATIC = 0x0138
WM_CTLCOLOREDIT = 0x0133
WM_CTLCOLORBTN = 0x0135
WM_COMMAND = 0x0111
WM_HOTKEY = 0x0312
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_APP = 0x8000
WM_TRAY = WM_APP + 1

# ---------------------------------------------------------------- 控件/窗口样式
WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_TABSTOP = 0x00010000
WS_VSCROLL = 0x00200000
WS_EX_TOPMOST = 0x00000008
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000

BS_OWNERDRAW = 0x0000000B
BS_PUSHBUTTON = 0x00000000
ES_MULTILINE = 0x0004
ES_READONLY = 0x0800
ES_AUTOVSCROLL = 0x0040
SS_LEFT = 0x00000000
SS_RIGHT = 0x00000002
SS_CENTER = 0x00000001

SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
SW_SHOWNORMAL = 1

# ---------------------------------------------------------------- 钩子
GA_ROOT = 2
WH_MOUSE_LL = 14
HC_ACTION = 0
WHEEL_DELTA = 120

# ---------------------------------------------------------------- 输入
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

# ---------------------------------------------------------------- 热键
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_R = 0x52

# ---------------------------------------------------------------- GDI
FW_NORMAL = 400
FW_SEMIBOLD = 600
FW_BOLD = 700
DEFAULT_CHARSET = 1
CLEARTYPE_QUALITY = 5
TRANSPARENT = 1
PS_SOLID = 0

DT_LEFT = 0x0000
DT_CENTER = 0x0001
DT_RIGHT = 0x0002
DT_VCENTER = 0x0004
DT_SINGLELINE = 0x0020
DT_WORDBREAK = 0x0010
DT_NOPREFIX = 0x0800

ODS_SELECTED = 0x0001
ODS_FOCUS = 0x0010
ODS_DISABLED = 0x0004

# ---------------------------------------------------------------- 结构体
class POINT(ctypes.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", w.LONG), ("top", w.LONG),
                ("right", w.LONG), ("bottom", w.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", w.DWORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD),
                ("dwFlags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", w.DWORD), ("u", _INPUTUNION)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", w.HWND), ("message", w.UINT),
                ("wParam", w.WPARAM), ("lParam", w.LPARAM),
                ("time", w.DWORD), ("pt", POINT)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", w.UINT), ("style", w.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH),
                ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR),
                ("hIconSm", w.HICON)]


class DRAWITEMSTRUCT(ctypes.Structure):
    _fields_ = [("CtlType", w.UINT), ("CtlID", w.UINT), ("itemID", w.UINT),
                ("itemAction", w.UINT), ("itemState", w.UINT),
                ("hwndItem", w.HWND), ("hDC", w.HDC), ("rcItem", RECT),
                ("itemData", ctypes.c_size_t)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", w.HDC), ("fErase", w.BOOL), ("rcPaint", RECT),
                ("fRestore", w.BOOL), ("fIncUpdate", w.BOOL),
                ("rgbReserved", ctypes.c_byte * 32)]


# ---------------------------------------------------------------- 绑定
def _bind():
    u = user32
    u.CreateWindowExW.argtypes = (w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE,
                                 ctypes.c_void_p)
    u.CreateWindowExW.restype = w.HWND
    u.DefWindowProcW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    u.DefWindowProcW.restype = LRESULT
    u.RegisterClassExW.argtypes = (ctypes.POINTER(WNDCLASSEXW),)
    u.RegisterClassExW.restype = w.WORD
    u.DestroyWindow.argtypes = (w.HWND,)
    u.ShowWindow.argtypes = (w.HWND, ctypes.c_int)
    u.UpdateWindow.argtypes = (w.HWND,)

    u.GetMessageW.argtypes = (ctypes.POINTER(MSG), w.HWND, w.UINT, w.UINT)
    u.GetMessageW.restype = ctypes.c_int
    u.PeekMessageW.argtypes = (ctypes.POINTER(MSG), w.HWND, w.UINT, w.UINT, w.UINT)
    u.PeekMessageW.restype = w.BOOL
    u.TranslateMessage.argtypes = (ctypes.POINTER(MSG),)
    u.DispatchMessageW.argtypes = (ctypes.POINTER(MSG),)
    u.DispatchMessageW.restype = LRESULT
    u.PostQuitMessage.argtypes = (ctypes.c_int,)
    u.PostMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    u.SendMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    u.SendMessageW.restype = LRESULT

    u.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, w.HINSTANCE, w.DWORD)
    u.SetWindowsHookExW.restype = ctypes.c_void_p
    u.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, w.WPARAM, w.LPARAM)
    u.CallNextHookEx.restype = LRESULT
    u.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
    u.UnhookWindowsHookEx.restype = w.BOOL

    u.SendInput.argtypes = (w.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    u.SendInput.restype = w.UINT
    u.GetCursorPos.argtypes = (ctypes.POINTER(POINT),)
    u.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
    u.WindowFromPoint.argtypes = (POINT,)
    u.WindowFromPoint.restype = w.HWND
    u.ScreenToClient.argtypes = (w.HWND, ctypes.POINTER(POINT))
    u.GetAncestor.argtypes = (w.HWND, w.UINT)
    u.GetAncestor.restype = w.HWND
    u.GetForegroundWindow.restype = w.HWND
    u.GetClassNameW.argtypes = (w.HWND, w.LPWSTR, ctypes.c_int)
    u.GetWindowTextW.argtypes = (w.HWND, w.LPWSTR, ctypes.c_int)
    u.GetWindowRect.argtypes = (w.HWND, ctypes.POINTER(RECT))
    u.GetClientRect.argtypes = (w.HWND, ctypes.POINTER(RECT))
    u.IsWindow.argtypes = (w.HWND,)
    u.IsWindow.restype = w.BOOL
    u.SetForegroundWindow.argtypes = (w.HWND,)
    # 激活目标窗口所需（Chromium / 游戏只在「激活状态」下才处理鼠标点击）
    u.BringWindowToTop.argtypes = (w.HWND,)
    u.AttachThreadInput.argtypes = (w.DWORD, w.DWORD, w.BOOL)
    u.GetWindowThreadProcessId.argtypes = (w.HWND, ctypes.POINTER(w.DWORD))
    u.GetWindowThreadProcessId.restype = w.DWORD
    u.SetWindowPos.argtypes = (w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, w.UINT)
    u.RegisterHotKey.argtypes = (w.HWND, ctypes.c_int, w.UINT, w.UINT)
    u.UnregisterHotKey.argtypes = (w.HWND, ctypes.c_int)
    u.InvalidateRect.argtypes = (w.HWND, ctypes.POINTER(RECT), w.BOOL)
    u.SetTimer.argtypes = (w.HWND, ctypes.c_size_t, w.UINT, ctypes.c_void_p)
    u.KillTimer.argtypes = (w.HWND, ctypes.c_size_t)
    u.GetSystemMetrics.argtypes = (ctypes.c_int,)
    u.SetWindowTextW.argtypes = (w.HWND, w.LPCWSTR)
    u.EnableWindow.argtypes = (w.HWND, w.BOOL)
    u.GetDC.argtypes = (w.HWND,)
    u.GetDC.restype = w.HDC
    u.ReleaseDC.argtypes = (w.HWND, w.HDC)
    u.GetKeyState.argtypes = (ctypes.c_int,)
    u.GetKeyState.restype = ctypes.c_short

    u.BeginPaint.argtypes = (w.HWND, ctypes.POINTER(PAINTSTRUCT))
    u.BeginPaint.restype = w.HDC
    u.EndPaint.argtypes = (w.HWND, ctypes.POINTER(PAINTSTRUCT))
    u.LoadCursorW.argtypes = (w.HINSTANCE, w.LPCWSTR)
    u.LoadCursorW.restype = w.HANDLE
    u.LoadIconW.argtypes = (w.HINSTANCE, w.LPCWSTR)
    u.LoadIconW.restype = w.HICON
    u.LoadImageW.argtypes = (w.HINSTANCE, w.LPCWSTR, w.UINT,
                             ctypes.c_int, ctypes.c_int, w.UINT)
    u.LoadImageW.restype = w.HANDLE
    u.AdjustWindowRectEx.argtypes = (ctypes.POINTER(RECT), w.DWORD, w.BOOL, w.DWORD)
    u.MessageBoxW.argtypes = (w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT)
    u.MessageBoxW.restype = ctypes.c_int
    u.ValidateRect.argtypes = (w.HWND, ctypes.POINTER(RECT))
    u.GetWindowLongW.argtypes = (w.HWND, ctypes.c_int)
    u.GetWindowLongW.restype = ctypes.c_long
    u.SetWindowLongW.argtypes = (w.HWND, ctypes.c_int, ctypes.c_long)
    u.SetWindowLongW.restype = ctypes.c_long
    # 注意：FillRect / DrawTextW 属于 user32，不是 gdi32
    u.FillRect.argtypes = (w.HDC, ctypes.POINTER(RECT), w.HBRUSH)
    u.FillRect.restype = ctypes.c_int
    u.DrawTextW.argtypes = (w.HDC, w.LPCWSTR, ctypes.c_int,
                            ctypes.POINTER(RECT), w.UINT)
    u.DrawTextW.restype = ctypes.c_int
    u.ShowWindow.argtypes = (w.HWND, ctypes.c_int)
    kernel32.GetCurrentProcess.restype = w.HANDLE
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentThreadId.restype = w.DWORD
    kernel32.GetCurrentThreadId.argtypes = ()
    kernel32.GetModuleHandleW.restype = w.HINSTANCE
    kernel32.GetModuleHandleW.argtypes = (w.LPCWSTR,)
    kernel32.TerminateProcess.argtypes = (w.HANDLE, w.UINT)
    kernel32.TerminateProcess.restype = w.BOOL
    # 取前台窗口所属进程的 exe 名，用于「只对指定游戏生效」
    kernel32.OpenProcess.argtypes = (w.DWORD, w.BOOL, w.DWORD)
    kernel32.OpenProcess.restype = w.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD))
    kernel32.QueryFullProcessImageNameW.restype = w.BOOL
    kernel32.CloseHandle.argtypes = (w.HANDLE,)
    kernel32.CloseHandle.restype = w.BOOL
    if dwmapi is not None:
        dwmapi.DwmSetWindowAttribute.argtypes = (w.HWND, w.DWORD,
                                                 ctypes.c_void_p, w.DWORD)
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

    g = gdi32
    g.CreateFontW.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, w.DWORD, w.DWORD, w.DWORD, w.DWORD,
                              w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR)
    g.CreateFontW.restype = w.HFONT
    g.CreateSolidBrush.argtypes = (w.COLORREF,)
    g.CreateSolidBrush.restype = w.HBRUSH
    g.CreatePen.argtypes = (ctypes.c_int, ctypes.c_int, w.COLORREF)
    g.CreatePen.restype = w.HPEN
    g.SelectObject.argtypes = (w.HDC, w.HGDIOBJ)
    g.SelectObject.restype = w.HGDIOBJ
    g.DeleteObject.argtypes = (w.HGDIOBJ,)
    g.SetBkMode.argtypes = (w.HDC, ctypes.c_int)
    g.SetTextColor.argtypes = (w.HDC, w.COLORREF)
    g.SetBkColor.argtypes = (w.HDC, w.COLORREF)
    g.RoundRect.argtypes = (w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int)


_bind()


def rgb(r, g, b):
    """把 RGB 转成 COLORREF。"""
    return r | (g << 8) | (b << 16)


def make_font(size_pt, weight=FW_NORMAL, name="Microsoft YaHei UI"):
    h = gdi32.CreateFontW(-int(size_pt * 96 / 72), 0, 0, 0, weight, 0, 0, 0,
                          DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, name)
    if not h:
        h = gdi32.CreateFontW(-int(size_pt * 96 / 72), 0, 0, 0, weight, 0, 0, 0,
                              DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "SimHei")
    return h
