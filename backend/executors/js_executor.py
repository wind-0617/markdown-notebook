"""JavaScript 执行器（FR-10，阶段二）。

依赖本机安装 Node.js；未安装时执行器会返回清晰的错误提示而非崩溃。
"""
from __future__ import annotations

from .base import BaseExecutor, register


class JavaScriptExecutor(BaseExecutor):
    language = "javascript"
    file_ext = ".js"

    def build_command(self, script_path: str) -> list[str]:
        return ["node", script_path]


register(JavaScriptExecutor())
