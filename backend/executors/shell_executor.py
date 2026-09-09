"""Shell 执行器（FR-10，阶段二）。

Windows 下使用 cmd /c，类 Unix 下使用 /bin/sh。
注意：Shell 代码可触达真实系统，生产环境务必启用 EXECUTOR_MODE=docker。
"""
from __future__ import annotations

import os

from .base import BaseExecutor, register


class ShellExecutor(BaseExecutor):
    language = "shell"
    file_ext = ".sh" if os.name != "nt" else ".bat"

    def build_command(self, script_path: str) -> list[str]:
        if os.name == "nt":
            return ["cmd", "/c", script_path]
        return ["/bin/sh", script_path]


register(ShellExecutor())
