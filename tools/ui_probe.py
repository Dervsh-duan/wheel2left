"""不启动引擎，只创建界面并截图，用于检查布局有没有重叠。

用法：python tools/ui_probe.py out.png [mode]
"""

import ctypes
import os
import struct
import sys
import time
import zlib
from ctypes import wintypes as w

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from app import App                       # noqa: E402
from w32 import MSG, RECT, gdi32, user32  # noqa: E402

PW_RENDERFULLCONTENT = 0x00000002
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
                ("biPlanes", w.WORD), ("biBitCount", w.WORD),
                ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG),
                ("biClrUsed", w.DWORD), ("biClrImportant", w.DWORD)]


gdi32.CreateCompatibleDC.argtypes = (w.HDC,)
gdi32.CreateCompatibleDC.restype = w.HDC
gdi32.CreateCompatibleBitmap.argtypes = (w.HDC, ctypes.c_int, ctypes.c_int)
gdi32.CreateCompatibleBitmap.restype = w.HBITMAP
gdi32.SelectObject.argtypes = (w.HDC, w.HGDIOBJ)
gdi32.SelectObject.restype = w.HGDIOBJ
gdi32.GetDIBits.argtypes = (w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), w.UINT)
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = (w.HGDIOBJ,)
gdi32.DeleteDC.argtypes = (w.HDC,)
gdi32.CreateSolidBrush.argtypes = (w.COLORREF,)
gdi32.CreateSolidBrush.restype = w.HBRUSH
user32.GetWindowRect.argtypes = (w.HWND, ctypes.POINTER(RECT))
user32.PrintWindow.argtypes = (w.HWND, w.HDC, w.UINT)
user32.PrintWindow.restype = w.BOOL
user32.GetDC.argtypes = (w.HWND,)
user32.GetDC.restype = w.HDC


def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def grab(hwnd, out):
    rc = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rc))
    ww, wh = rc.right - rc.left, rc.bottom - rc.top
    ref = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(ref)
    bmp = gdi32.CreateCompatibleBitmap(ref, ww, wh)
    old = gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = ww
    bi.biHeight = -wh
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(ww * wh * 4)
    gdi32.GetDIBits(mem, bmp, 0, wh, buf, ctypes.byref(bi), DIB_RGB_COLORS)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)

    raw = bytearray()
    src = buf.raw
    for row in range(wh):
        raw.append(0)
        base = row * ww * 4
        for col in range(ww):
            i = base + col * 4
            raw += bytes((src[i + 2], src[i + 1], src[i], 255))
    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", ww, wh, 8, 6, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(bytes(raw), 6)) +
           chunk(b"IEND", b""))
    with open(out, "wb") as f:
        f.write(png)
    print(f"PrintWindow={bool(ok)} saved {out} {ww}x{wh}")


def pump(seconds):
    msg = MSG()
    end = time.time() + seconds
    while time.time() < end:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.02)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "ui.png"
    from engine import Engine, MODE_TARGET

    app = App()
    # 造一个不启动驱动的引擎，只为把界面填满内容，检查排版
    app.engine = Engine(on_log=app.log, on_state=lambda: None)
    app.engine.mode = MODE_TARGET
    app.engine.targets = {"game.exe"}
    app.engine.fired = 42
    app.engine.skipped = 3
    app.engine.last_foreground = "game.exe"
    app.hotkey_ok = True
    app.log("驱动已接管滚轮 · 范围：指定程序")
    app.log("目标程序：game.exe")
    app.log("已锁定「game.exe」，只有它的滚轮会变成左键")
    hwnd = app.create()
    app.drain_logs()
    pump(0.8)
    grab(hwnd, out)
    user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
    pump(0.3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
