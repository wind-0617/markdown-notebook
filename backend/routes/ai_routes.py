"""AI API（FR-11）：对话、连接测试（功能四）、聊天记录读写（功能五）。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import (
    E_AI_NOT_CONFIGURED,
    E_AI_UPSTREAM,
    E_BAD_REQUEST,
    E_NAME_INVALID,
    ok,
    fail,
)
from deps import ai_service
from services import NoteError

bp = Blueprint("ai", __name__)


def _ai_error(result: dict):
    """AIResult → 信封失败响应（not_configured 显式标志，不再靠文案猜测）。"""
    error = result.get("error") or "AI 调用失败"
    if result.get("not_configured"):
        return fail(E_AI_NOT_CONFIGURED, error)
    return fail(E_AI_UPSTREAM, error, status=502)


def _overrides(payload: dict):
    ai = payload.get("ai")
    return ai if isinstance(ai, dict) and any(ai.values()) else None


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

    result = ai_service.chat(
        messages, context=payload.get("context", ""), overrides=_overrides(payload)
    )
    if result.get("ok"):
        return ok({"reply": result.get("reply"), "model": result.get("model")})
    return _ai_error(result)


@bp.post("/api/ai/test")
def api_ai_test():
    """功能四：测试连接。body 可带 {ai:{base_url,api_key,model}}；不带则测服务端 env 配置。"""
    payload = request.get_json(silent=True) or {}
    result = ai_service.test_connection(overrides=_overrides(payload))
    if result.get("ok"):
        return ok({"message": "连接成功", "model": result.get("model"),
                   "echo": result.get("reply")})
    return _ai_error(result)


# ---- 聊天记录（功能五）：与笔记同名，存 notebooks/<stem>.ai-chat.json ----
def _chat_fail(exc: NoteError):
    msg = str(exc)
    if "不合法" in msg or "非法" in msg:
        return fail(E_NAME_INVALID, msg)
    return fail(E_BAD_REQUEST, msg)


@bp.get("/api/ai/chat/<name>")
def api_chat_load(name: str):
    try:
        return ok(ai_service.load_chat(name))
    except NoteError as exc:
        return _chat_fail(exc)


@bp.post("/api/ai/chat/<name>")
def api_chat_save(name: str):
    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload.get("messages"), list):
        return fail(E_BAD_REQUEST, "请求体必须是 {messages: [...]}")
    try:
        return ok(ai_service.save_chat(name, payload["messages"]))
    except NoteError as exc:
        return _chat_fail(exc)


@bp.delete("/api/ai/chat/<name>")
def api_chat_clear(name: str):
    try:
        return ok(ai_service.clear_chat(name))
    except NoteError as exc:
        return _chat_fail(exc)
