"""把 dist 产物 + 驱动 + 脚本打成一个可发布的压缩包。

用法：python tools/make_release.py [版本号]
产物：release/Wheel2Left-v<版本>-win64.zip
"""

import hashlib
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIST = os.path.join(ROOT, "dist")
REL = os.path.join(ROOT, "release")

EXE = "Wheel2Left.exe"
DLL = "interception.dll"
DRIVER_DIR = os.path.join(ROOT, "driver", "Interception")

TOP_FILES = ["使用说明.txt", "LICENSE", "THIRD_PARTY_NOTICES.md",
             "install_driver.bat", "uninstall_driver.bat"]


def version_from_info():
    try:
        with open(os.path.join(ROOT, "version_info.txt"), encoding="utf-8") as f:
            m = re.search(r"filevers=\((\d+),\s*(\d+),\s*(\d+)", f.read())
        if m:
            return ".".join(m.groups())
    except Exception:
        pass
    return "0.0.0"


def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else version_from_info()
    tag = f"Wheel2Left-v{ver}-win64"
    stage = os.path.join(REL, tag)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    missing = []
    for name in TOP_FILES:
        src = os.path.join(ROOT, name)
        if not os.path.exists(src):
            missing.append(name)
            continue
        shutil.copy2(src, os.path.join(stage, name))
    # exe 和 dll 在 dist 里
    for name in (EXE, DLL):
        src = os.path.join(DIST, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(stage, name))
        elif name not in missing:
            missing.append("dist/" + name)
    if missing:
        print("[warn] 缺少文件：" + ", ".join(missing))

    if os.path.isdir(DRIVER_DIR):
        shutil.copytree(DRIVER_DIR, os.path.join(stage, "Interception"))
    else:
        print("[warn] 缺少 driver/Interception，压缩包将不含驱动安装文件")

    # tests 目录里放一份构建自检脚本？不需要，保持包干净
    zip_path = os.path.join(REL, tag + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, _dirs, files in os.walk(stage):
            for fn in files:
                full = os.path.join(base, fn)
                arc = os.path.join(tag, os.path.relpath(full, stage))
                z.write(full, arc)

    size = os.path.getsize(zip_path)
    h = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"[ok] {zip_path}")
    print(f"     {size / 1048576:.2f} MB")
    print(f"     sha256 {h.hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
