"""代码执行 API（FR-03/08/10）：语言分发 + 交互参数注入 + 环境预检。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import E_BAD_REQUEST, E_ENV_UNAVAILABLE, E_LANG_UNSUPPORTED, ok, fail
from config import Config
from executors import get_executor, supported_languages
from parsers.param_parser import build_executable_code
from services import environment

bp = Blueprint("execute", __name__)


@bp.post("/api/execute")
def api_execute():
    payload = request.get_json(silent=True) or {}
    language = (payload.get("language") or "python").strip().lower()
    code = payload.get("code") or ""
    params = payload.get("params") or {}
    timeout = payload.get("timeout")

    executor = get_executor(language)
    if executor is None:
        return fail(
            E_LANG_UNSUPPORTED,
            f"暂不支持语言：{language}",
            status=400,
            details={"languages": supported_languages()},
        )

    # java/go 单文件源码模式没有合法的“文件头注入赋值”语法位（见 dev_log）
    if params and language in ("java", "go"):
        return fail(
            E_BAD_REQUEST,
            f"{language} 代码块暂不支持交互参数（仅 python/javascript/shell），请直接在代码中声明变量",
        )

    # 环境预检：解释器缺失时直接给安装引导，省一次注定失败的子进程调用
    env = environment.check(language)
    if not env.get("available"):
        return fail(
            E_ENV_UNAVAILABLE,
            env.get("hint") or f"本机未检测到 {language} 运行环境",
            status=424,
            details={"environment": env},
        )

    if params:
        code = build_executable_code(language, code, params)

    result = executor.run(
        code,
        timeout=timeout,
        mode=Config.EXECUTOR_MODE,
        docker_image=Config.DOCKER_SANDBOX_IMAGE,
        memory_limit=Config.DOCKER_MEMORY_LIMIT,
        cpu_limit=Config.DOCKER_CPU_LIMIT,
    )
    return ok(result.to_dict())
