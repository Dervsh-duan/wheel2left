"""端到端冒烟测试（需管理员）：真的启动引擎，跑 4 秒然后正常退出。

验证点：驱动上下文能建、config 能读、UI 能画、退出干净。
用法（管理员）：python tools/smoke.py [输出日志路径]
"""

import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "smoke.txt")
_lines = []


def say(msg):
    _lines.append(str(msg))
    try:
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def main():
    try:
        os.remove(OUT)
    except Exception:
        pass
    say("== smoke start ==")
    try:
        from app import App
        from engine import MODE_NAMES
        from w32 import user32
    except Exception as e:
        say(f"[fail] import: {type(e).__name__}: {e}")
        return 1

    app = App()
    try:
        hwnd = app.create()
    except Exception as e:
        say(f"[fail] create: {e}")
        return 1
    say(f"[ok] hwnd={hwnd}")

    def shut():
        time.sleep(3.0)
        e = app.engine
        say(f"[info] last_foreground={e.last_foreground!r} mode={e.mode}")
        app._lock_foreground()
        time.sleep(0.4)
        say(f"[info] 锁定后 mode={e.mode} targets={sorted(e.targets)}")
        from config import load
        say(f"[info] 磁盘配置 = {load()}")
        say(f"[info] fired={e.fired} dropped={e.dropped} skipped={e.skipped}")
        user32.PostMessageW(hwnd, 0x0010, 0, 0)

    threading.Thread(target=shut, daemon=True).start()
    t0 = time.time()
    rc = app.run()
    say(f"[ok] run 退出 rc={rc} 用时 {time.time() - t0:.2f}s")
    say("== smoke end ==")
    return rc


if __name__ == "__main__":
    sys.exit(main())
