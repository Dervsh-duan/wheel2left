"""用 PrintWindow 直接把指定窗口渲染成图片，不依赖屏幕抓取。

这样即使游戏独占全屏覆盖了桌面，也能检查我们自己的窗口画得对不对。
用法：python shot_window.py 窗口类名 输出.png
"""

import ctypes
import struct
import sys
import zlib
from ctypes import wintypes as w

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

PW_RENDERFULLCONTENT = 0x00000002
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
                ("biPlanes", w.WORD), ("biBitCount", w.WORD),
                ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG),
                ("biClrUsed", w.DWORD), ("biClrImportant", w.DWORD)]


class RECT(ctypes.Structure):
    _fields_ = [("left", w.LONG), ("top", w.LONG), ("right", w.LONG), ("bottom", w.LONG)]


user32.FindWindowW.argtypes = (w.LPCWSTR, w.LPCWSTR)
user32.FindWindowW.restype = w.HWND
user32.IsWindowVisible.argtypes = (w.HWND,)
user32.IsWindowVisible.restype = w.BOOL
user32.GetWindowRect.argtypes = (w.HWND, ctypes.POINTER(RECT))
user32.PrintWindow.argtypes = (w.HWND, w.HDC, w.UINT)
user32.PrintWindow.restype = w.BOOL
user32.GetWindowTextW.argtypes = (w.HWND, w.LPWSTR, ctypes.c_int)
user32.GetDC.argtypes = (w.HWND,)
user32.GetDC.restype = w.HDC
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


def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def main():
    cls = sys.argv[1] if len(sys.argv) > 1 else "W2RC_Main"
    out = sys.argv[2] if len(sys.argv) > 2 else "window.png"

    hwnd = user32.FindWindowW(cls, None)
    if not hwnd:
        print(f"找不到窗口：{cls}")
        return 1
    title = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(hwnd, title, 128)
    rc = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rc))
    ww, wh = rc.right - rc.left, rc.bottom - rc.top
    print(f"hwnd={hwnd} title={title.value!r} visible={bool(user32.IsWindowVisible(hwnd))} "
          f"rect=({rc.left},{rc.top},{ww}x{wh})")

    ref = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(ref)
    bmp = gdi32.CreateCompatibleBitmap(ref, ww, wh)
    old = gdi32.SelectObject(mem, bmp)

    ok = user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
    print(f"PrintWindow -> {bool(ok)}")

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
    print(f"saved {out} {ww}x{wh}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
