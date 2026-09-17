"""AI 对话 API（FR-11）。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import E_AI_NOT_CONFIGURED, E_AI_UPSTREAM, E_BAD_REQUEST, ok, fail
from deps import ai_service

bp = Blueprint("ai", __name__)


@bp.post("/api/ai/chat")
def api_ai_chat():
    payload = request.get_json(silent=True)
    if payload is None:
        return fail(E_BAD_REQUEST, "请求体必须是 JSON")
    messages = payload.get("messages") or []
    if not messages and payload.get("question"):      # 契约别名：question ≈ prompt
        messages = [{"role": "user", "content": payload["question"]}]
    if not messages and payload.get("prompt"):
        messages = [{"role": "user", "content": payload["prompt"]}]
    if not messages:
        return fail(E_BAD_REQUEST, "messages/question 均为空")

    # ai: {base_url, model, api_key} —— 浏览器端配置覆盖 env 默认（仅本机转发，不落盘不回显）
    result = ai_service.chat(
        messages, context=payload.get("context", ""), overrides=payload.get("ai")
    )
    if result.get("ok"):
        return ok({"reply": result.get("reply"), "model": result.get("model")})
    error = result.get("error") or "AI 调用失败"
    code = E_AI_NOT_CONFIGURED if ("配置" in error or "未安装" in error) else E_AI_UPSTREAM
    return fail(code, error, status=400 if code == E_AI_NOT_CONFIGURED else 502)
