"""统一 API 响应信封（指令文档·六）。

成功：{"success": true, "data": ..., "error": null}
失败：{"success": false, "data": null, "error": {"code": "ERROR_CODE", "message": "..."}}

所有 /api 路由必须经由 ok()/fail() 返回，禁止裸 jsonify。
"""
from __future__ import annotations

from flask import jsonify


def ok(data=None, status: int = 200):
    return jsonify({"success": True, "data": data, "error": None}), status


def fail(code: str, message: str, status: int = 400, details=None):
    payload = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return jsonify({"success": False, "data": None, "error": payload}), status


# ---- 稳定错误码表（前端按 code 做差异化处理，message 供人读） ----
E_BAD_REQUEST = "BAD_REQUEST"
E_NOT_FOUND = "NOT_FOUND"
E_NAME_INVALID = "NOTE_NAME_INVALID"
E_NOTE_EXISTS = "NOTE_EXISTS"
E_LANG_UNSUPPORTED = "LANGUAGE_UNSUPPORTED"
E_ENV_UNAVAILABLE = "ENVIRONMENT_UNAVAILABLE"
E_AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
E_AI_UPSTREAM = "AI_UPSTREAM_ERROR"
E_GIT_ERROR = "GIT_ERROR"
E_SEARCH_ERROR = "SEARCH_ERROR"
E_FILE_TOO_LARGE = "FILE_TOO_LARGE"
E_INTERNAL = "INTERNAL"
