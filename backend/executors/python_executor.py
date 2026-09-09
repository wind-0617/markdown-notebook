"""Python 执行器（FR-03，阶段一核心）。

本机模式使用隔离参数执行脚本文件（绝不经过 shell 解释）：
  -I  隔离模式（忽略用户 site-packages 与环境注入；注意 -I 不含 -E！）
  -E  忽略 PYTHON* 环境变量（研究 flask-jupyter 时核实：-I 挡不住 PYTHONPATH）
  -B  不写字节码缓存

PyInstaller 打包后 sys.executable 就是本程序 exe —— 直接调用会自我递归启动，
必须改为探测用户机器上的真实 Python（NB_PYTHON 环境变量可显式指定）。
"""
from __future__ import annotations

import os
import shutil
import sys

from .base import BaseExecutor, register


def _resolve_interpreter() -> str:
    """返回可用的 python 解释器路径；找不到时抛 FileNotFoundError。"""
    if not getattr(sys, "frozen", False):
        return sys.executable

    env = os.environ.get("NB_PYTHON", "").strip()
    if env:
        if os.path.isfile(env):
            return env
        raise FileNotFoundError(f"NB_PYTHON 指向的文件不存在：{env}")

    meipass = getattr(sys, "_MEIPASS", "")
    exe_abs = os.path.abspath(sys.executable)
    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if not found:
            continue
        abs_p = os.path.abspath(found)
        # 排除 exe 自身与解包临时目录，防自我递归
        if abs_p == exe_abs:
            continue
        if meipass and abs_p.startswith(os.path.abspath(meipass)):
            continue
        if os.path.isfile(abs_p):
            return abs_p
    raise FileNotFoundError(
        "打包版未在本机找到 Python 解释器。请：\n"
        "  1) 安装 Python 3 并勾选 “Add to PATH”，或\n"
        "  2) 设置环境变量 NB_PYTHON 指向 python.exe，或\n"
        "  3) 改用 Docker 沙箱执行模式（EXECUTOR_MODE=docker）。"
    )


class PythonExecutor(BaseExecutor):
    language = "python"
    file_ext = ".py"

    def build_command(self, script_path: str) -> list[str]:
        return [_resolve_interpreter(), "-I", "-E", "-B", script_path]


register(PythonExecutor())
