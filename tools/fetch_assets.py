#!/usr/bin/env python3
"""fetch_assets.py —— 把前端 CDN 依赖镜像到 frontend/vendor/，供离线打包。

目录结构与 jsdelivr URL 路径一一对应（index.html 中 __ASSET_BASE__ 会被后端
替换为 "/vendor"（存在本目录时）或 CDN 域名（开发态默认））：

  frontend/vendor/
  ├── npm/marked@12.0.0/marked.min.js
  ├── npm/monaco-editor@0.45.0/min/vs/**          (解自 npm registry tarball)
  └── gh/highlightjs/cdn-release@11.9.0/build/
      ├── highlight.min.js
      └── styles/github.min.css · styles/github-dark.min.css

用法：
  python tools/fetch_assets.py           # 幂等，已存在的文件跳过
  python tools/fetch_assets.py --force   # 清空重下

国内网络可设置环境变量使用镜像（仅替换 npm registry 与 jsdelivr 主机名）：
  NPM_REGISTRY_URL=https://registry.npmmirror.com
  CDN_BASE_URL=https://testingcf.jsdelivr.net
"""
from __future__ import annotations

import os
import shutil
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "frontend", "vendor")
CDN = os.environ.get("CDN_BASE_URL", "https://cdn.jsdelivr.net").rstrip("/")
NPM_REGISTRY = os.environ.get("NPM_REGISTRY_URL", "https://registry.npmjs.org").rstrip("/")

MONACO_VERSION = "0.45.0"
MARKED_VERSION = "12.0.0"
HLJS_VERSION = "11.9.0"

# (目标相对路径, 源 URL) —— 单文件直下
FILES = [
    (
        f"npm/marked@{MARKED_VERSION}/marked.min.js",
        f"{CDN}/npm/marked@{MARKED_VERSION}/marked.min.js",
    ),
    (
        f"gh/highlightjs/cdn-release@{HLJS_VERSION}/build/highlight.min.js",
        f"{CDN}/gh/highlightjs/cdn-release@{HLJS_VERSION}/build/highlight.min.js",
    ),
    (
        f"gh/highlightjs/cdn-release@{HLJS_VERSION}/build/styles/github.min.css",
        f"{CDN}/gh/highlightjs/cdn-release@{HLJS_VERSION}/build/styles/github.min.css",
    ),
    (
        f"gh/highlightjs/cdn-release@{HLJS_VERSION}/build/styles/github-dark.min.css",
        f"{CDN}/gh/highlightjs/cdn-release@{HLJS_VERSION}/build/styles/github-dark.min.css",
    ),
]

MONACO_PREFIX = f"npm/monaco-editor@{MONACO_VERSION}/min/vs"
MONACO_TARBALL = f"{NPM_REGISTRY}/monaco-editor/-/monaco-editor-{MONACO_VERSION}.tgz"

# Windows GBK 控制台/管道下打印 emoji 会崩，统一 UTF-8 兜底
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def download(url: str, dest: str) -> bool:
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  ↓ {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "markdown-notebook-builder"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest + ".part", "wb") as f:
        shutil.copyfileobj(resp, f)
    os.replace(dest + ".part", dest)
    return True


def fetch_monaco() -> int:
    """从 npm 官方 tarball 解出 min/vs 整目录（jsdelivr 不提供目录打包）。"""
    marker = os.path.join(VENDOR, MONACO_PREFIX, "loader.js")
    if os.path.isfile(marker):
        return 0
    tgz = os.path.join(VENDOR, "_monaco.tgz")
    os.makedirs(VENDOR, exist_ok=True)
    print(f"  ↓ {MONACO_TARBALL}  (Monaco 完整包，约 10MB)")
    req = urllib.request.Request(MONACO_TARBALL, headers={"User-Agent": "markdown-notebook-builder"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(tgz + ".part", "wb") as f:
        shutil.copyfileobj(resp, f)
    os.replace(tgz + ".part", tgz)

    count = 0
    with tarfile.open(tgz, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.startswith("package/min/vs/"):
                continue
            rel = member.name[len("package/"):]                     # min/vs/...
            out = os.path.join(VENDOR, f"npm/monaco-editor@{MONACO_VERSION}", rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with tar.extractfile(member) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    os.remove(tgz)
    if count == 0 or not os.path.isfile(marker):
        raise RuntimeError("Monaco 解包失败：tarball 中未找到 package/min/vs")
    return count


def main() -> int:
    force = "--force" in sys.argv
    if force and os.path.isdir(VENDOR):
        shutil.rmtree(VENDOR)
        print("🧹 已清空 frontend/vendor/")

    print("📦 镜像前端静态依赖 → frontend/vendor/")
    n = 0
    for rel, url in FILES:
        if download(url, os.path.join(VENDOR, rel)):
            n += 1
    mono = fetch_monaco()
    total_files = sum(len(fs) for _, _, fs in os.walk(VENDOR))
    print(f"✅ 完成：新增单文件 {n} 个，Monaco 解出 {mono} 个文件，vendor 共 {total_files} 个文件")

    # 校验关键标记文件
    for marker in [
        f"npm/marked@{MARKED_VERSION}/marked.min.js",
        f"npm/monaco-editor@{MONACO_VERSION}/min/vs/loader.js",
        f"npm/monaco-editor@{MONACO_VERSION}/min/vs/editor/editor.main.js",
        f"gh/highlightjs/cdn-release@{HLJS_VERSION}/build/highlight.min.js",
    ]:
        path = os.path.join(VENDOR, *marker.split("/"))
        if not os.path.isfile(path):
            print(f"❌ 缺少关键文件：{marker}")
            return 1
    print("✅ 完整性校验通过（后端检测到 vendor/ 会自动切换离线模式）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
