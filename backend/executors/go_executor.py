"""Go 执行器（指令文档·九.4）：`go run main.go`，需代码含 func main()。"""
from __future__ import annotations

import os
import shutil

from .base import BaseExecutor, register


class GoExecutor(BaseExecutor):
    language = "go"
    file_ext = ".go"

    def build_command(self, script_path: str) -> list[str]:
        go = os.environ.get("NB_GO", "").strip() or shutil.which("go") or "go"
        return [go, "run", script_path]


register(GoExecutor())
