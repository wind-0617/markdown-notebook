#!/usr/bin/env python3
"""package_dist.py —— 组装 GitHub Release 用的 zip 产物。

  dist/markdown-notebook-windows-x64.zip
  ├── markdown-notebook.exe        （PyInstaller 单文件产物）
  ├── 使用说明.txt                  （源自 packaging/使用说明.txt）
  └── notebooks/示例笔记.md         （开箱可导入的示例，数据不进 exe）

用法：pyinstaller 构建完成后执行 `python tools/package_dist.py`。
"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
EXE = os.path.join(DIST, "markdown-notebook.exe")
STAGING = os.path.join(DIST, "markdown-notebook-windows-x64")
ZIP = os.path.join(DIST, "markdown-notebook-windows-x64.zip")

PAYLOAD = [
    (EXE, "markdown-notebook.exe"),
    (os.path.join(ROOT, "packaging", "使用说明.txt"), "使用说明.txt"),
    (os.path.join(ROOT, "backend", "notebooks", "示例笔记.md"),
     os.path.join("notebooks", "示例笔记.md")),
]

# Windows GBK 控制台/管道下打印 emoji/中文会崩，统一 UTF-8 兜底
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    if not os.path.isfile(EXE):
        print("❌ 未找到 dist/markdown-notebook.exe，请先运行 build.bat 或 pyinstaller")
        return 1
    shutil.rmtree(STAGING, ignore_errors=True)
    if os.path.isfile(ZIP):
        os.remove(ZIP)

    for src, rel in PAYLOAD:
        if not os.path.isfile(src):
            print(f"❌ 缺少产物文件：{src}")
            return 1
        dst = os.path.join(STAGING, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, _ in [(rel, src) for src, rel in PAYLOAD]:
            zf.write(os.path.join(STAGING, rel), rel)

    size_mb = os.path.getsize(ZIP) / 1024 / 1024
    print(f"✅ 产物就绪：{ZIP}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
