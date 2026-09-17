"""执行引擎包：导入即完成各语言执行器的注册。"""
from __future__ import annotations

from .base import BaseExecutor, ExecutionResult, get_executor, register, supported_languages

# 导入副作用：注册内置执行器
from . import python_executor  # noqa: F401,E402
from . import js_executor  # noqa: F401,E402
from . import shell_executor  # noqa: F401,E402
from . import java_executor  # noqa: F401,E402
from . import go_executor  # noqa: F401,E402

__all__ = [
    "BaseExecutor",
    "ExecutionResult",
    "get_executor",
    "register",
    "supported_languages",
]
