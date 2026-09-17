"""运行环境探测服务：/api/environment/check 与 /api/health 的语言状态来源。

每种语言一个探测命令（60s 缓存），返回 {available, version, hint}。
hint 仅在不可用时给出——前端据此渲染安装引导（指令文档·九.4）。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time

from executors.python_executor import resolve_interpreter_path

_CACHE_TTL = 60.0
_cache: dict[str, tuple[float, dict]] = {}


def _run_version(argv: list[str]) -> str | None:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=6,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0 and out.strip():
            return out.strip().splitlines()[0].strip()[:120]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _probe_python() -> dict:
    hint = "安装 Python 3（勾选 Add to PATH）：https://www.python.org/downloads/"
    try:
        exe = resolve_interpreter_path()
    except FileNotFoundError:
        return {"available": False, "version": None, "hint": hint}
    ver = _run_version([exe, "-V"])
    return {"available": bool(ver), "version": ver, "hint": None if ver else hint,
            "path": exe}


def _probe_node() -> dict:
    node = shutil.which("node")
    if not node:
        return {"available": False, "version": None,
                "hint": "安装 Node.js LTS：https://nodejs.org/"}
    return {"available": True, "version": _run_version([node, "-v"]), "path": node}


def _probe_shell() -> dict:
    if sys.platform == "win32":
        return {"available": True, "version": "cmd.exe", "hint": None}
    return {"available": True, "version": "/bin/sh", "hint": None}


def _probe_java() -> dict:
    hint = "需要 JDK 11+（java 需支持单文件源码启动）：https://adoptium.net/"
    java = shutil.which("java")
    if not java:
        return {"available": False, "version": None, "hint": hint}
    ver = _run_version([java, "--version"]) or _run_version([java, "-version"])
    ok = False
    if ver:
        # JDK 8: 'java version "1.8.0_x"'；JDK 9+: 'java 21.0.6 …' / 'openjdk 17 …'
        m = re.search(r'version\s+"?(\d+)', ver) or re.match(r"(?:openjdk|java)\s+(\d+)", ver)
        if m:
            major = int(m.group(1))
            ok = major >= 11 if major != 1 else False  # 1.8 这类老版单文件启动不支持
    return {"available": ok, "version": ver, "hint": None if ok else hint, "path": java}


def _probe_go() -> dict:
    hint = "安装 Go：https://go.dev/dl/"
    go = shutil.which("go")
    if not go:
        return {"available": False, "version": None, "hint": hint}
    ver = _run_version([go, "version"])
    return {"available": bool(ver), "version": ver, "hint": None if ver else hint,
            "path": go}


PROBES = {
    "python": _probe_python,
    "javascript": _probe_node,
    "shell": _probe_shell,
    "java": _probe_java,
    "go": _probe_go,
}
ALIAS = {"js": "javascript", "bash": "shell", "sh": "shell", "py": "python",
         "node": "javascript", "cmd": "shell"}


def check(language: str) -> dict:
    key = ALIAS.get((language or "").strip().lower(), (language or "").strip().lower())
    probe = PROBES.get(key)
    if probe is None:
        return {"language": key, "available": False, "version": None,
                "hint": f"暂不支持语言：{key}"}
    now = time.monotonic()
    hit = _cache.get(key)
    if not hit or now - hit[0] > _CACHE_TTL or not hit[1].get("available"):
        data = probe()
        data["language"] = key
        _cache[key] = (now, data)
    else:
        data = hit[1]
    return dict(data)


def check_all() -> dict:
    return {key: check(key) for key in PROBES}
