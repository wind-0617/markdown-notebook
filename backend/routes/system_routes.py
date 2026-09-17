"""系统类 API：健康检查 / 环境探测。"""
from __future__ import annotations

import os

from flask import Blueprint, request

from api_response import E_BAD_REQUEST, ok, fail
from config import Config
from deps import ai_service
from executors import supported_languages
from services import environment

bp = Blueprint("system", __name__)

VERSION = "0.3.1"


@bp.get("/api/health")
def api_health():
    langs = environment.check_all()
    return ok(
        {
            "version": VERSION,
            "frozen": Config.FROZEN,
            "notebooks_dir": Config.NOTEBOOKS_DIR,
            "frontend_bundled": bool(Config.FROZEN)
            or os.path.isfile(os.path.join(Config.FRONTEND_DIST_DIR, "index.html")),
            "executor_mode": Config.EXECUTOR_MODE,
            "languages": [
                {
                    "language": lang,
                    "registered": lang in supported_languages(),
                    "available": (langs.get(lang) or {}).get("available", False),
                    "version": (langs.get(lang) or {}).get("version"),
                    "hint": (langs.get(lang) or {}).get("hint"),
                }
                for lang in sorted(langs)
            ],
            "ai_configured": ai_service.enabled,
        }
    )


@bp.get("/api/environment/check")
def api_environment_check():
    lang = (request.args.get("lang") or "").strip()
    if not lang:
        return fail(E_BAD_REQUEST, "缺少参数 lang，例如 /api/environment/check?lang=java")
    data = environment.check(lang)
    return ok(data)
