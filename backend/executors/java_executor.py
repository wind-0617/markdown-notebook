"""Java 执行器（指令文档·九.4）。

JDK 11+ 单文件源码启动：`java Main.java`（免显式 javac），
要求代码中的公共类名为 Main（前端示例与文档已提示）。
环境未安装时由 /api/environment/check 提前给出安装引导，执行层再兜底报错。
"""
from __future__ import annotations

import os
import shutil

from .base import BaseExecutor, register


class JavaExecutor(BaseExecutor):
    language = "java"
    file_ext = ".java"

    def build_command(self, script_path: str) -> list[str]:
        java = os.environ.get("NB_JAVA", "").strip() or shutil.which("java") or "java"
        return [java, script_path]


register(JavaExecutor())
