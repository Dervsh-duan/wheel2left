"""配置持久化：记住上次的生效范围和目标程序列表。

存到 %LOCALAPPDATA%\\Wheel2Left\\config.json，不放在 exe 旁边 —— 因为
exe 可能被放在 Program Files 这类没有写权限的目录里。
"""

import json
import os

MODES = ("global", "fullscreen", "target")
DEFAULT_MODE = "target"     # 默认只对锁定的程序生效，避免在桌面误点图标


def config_dir():
    base = (os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or os.path.expanduser("~"))
    d = os.path.join(base, "Wheel2Left")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def config_path():
    return os.path.join(config_dir(), "config.json")


def load():
    """读配置，任何异常都退回默认值 —— 配置坏了不该让程序起不来。"""
    try:
        with open(config_path(), encoding="utf-8") as f:
            data = json.load(f)
        mode = data.get("mode")
        if mode not in MODES:
            mode = DEFAULT_MODE
        targets = {str(t).strip().lower()
                   for t in (data.get("targets") or []) if str(t).strip()}
        return mode, targets
    except Exception:
        return DEFAULT_MODE, set()


def save(mode, targets):
    """原子写入：先写临时文件再 replace，避免断电留下半个 json。"""
    p = config_path()
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "targets": sorted(targets)},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        return True
    except Exception:
        return False
