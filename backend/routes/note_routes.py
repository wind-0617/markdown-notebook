"""笔记 CRUD + 重命名/删除/导出 API（FR-05，功能一/二/三）。

写操作后同步全文检索索引（九.3）；删除/重命名同步处理随笔记绑定的
AI 聊天记录（<同名>.ai-chat.json，功能五约定）。
"""
from __future__ import annotations

import os

from flask import Blueprint, request, send_from_directory

from api_response import (
    E_BAD_REQUEST,
    E_FILE_TOO_LARGE,
    E_NAME_INVALID,
    E_NOT_FOUND,
    E_NOTE_EXISTS,
    ok,
    fail,
)
from deps import ai_service, note_service, search_service
from services import NoteError

bp = Blueprint("notes", __name__)

EXPORT_MAX_BYTES = 10 * 1024 * 1024      # 导出体积护栏（安全·七）


def _index(name: str) -> None:
    """索引失败绝不影响笔记主流程，仅在开发日志级别记录。"""
    try:
        search_service.index_note(name)
    except Exception as exc:  # noqa: BLE001
        print(f"[search] index_note({name}) 失败：{exc}")


def _note_fail(exc: NoteError, *, missing_status: int = 400):
    """NoteError → 按语义映射错误码（message 供人读，code 供程序分支）。"""
    msg = str(exc)
    if "不存在" in msg:
        return fail(E_NOT_FOUND, msg, status=missing_status)
    if "不合法" in msg or "非法" in msg:
        return fail(E_NAME_INVALID, msg)
    if "已存在" in msg:
        return fail(E_NOTE_EXISTS, msg)
    return fail(E_BAD_REQUEST, msg)


@bp.get("/api/notes")
def api_notes_list():
    return ok({"notes": note_service.list_notes()})


# ---- 重命名（功能一）。静态路由必须先于 /api/notes/<name> 定义以避免歧义 --
@bp.post("/api/notes/rename")
def api_notes_rename():
    payload = request.get_json(silent=True)
    if payload is None:
        return fail(E_BAD_REQUEST, "请求体必须是 JSON")
    try:
        data = note_service.rename_note(payload.get("old_path", ""), payload.get("new_name", ""))
    except NoteError as exc:
        return _note_fail(exc)
    # 聊天记录跟随迁移（失败不阻断改名主流程）
    try:
        ai_service.rename_chat(data["old_name"], data["name"])
    except Exception as exc:  # noqa: BLE001
        print(f"[chat] rename_chat 失败：{exc}")
    try:
        search_service.remove_note(data["old_name"])
    except Exception as exc:  # noqa: BLE001
        print(f"[search] remove_note 失败：{exc}")
    _index(data["name"])
    return ok(data)


# ---- 导出下载（功能三）：文件流 + attachment 头，中文文件名走 RFC 5987 --
@bp.get("/api/notes/<name>/export")
def api_notes_export(name: str):
    try:
        real, path = note_service.prepare_export(name)
    except NoteError as exc:
        return _note_fail(exc, missing_status=404)
    size = os.path.getsize(path)
    if size > EXPORT_MAX_BYTES:
        return fail(E_FILE_TOO_LARGE, f"笔记过大（{size} 字节），暂不直接导出", status=413)
    return send_from_directory(
        os.path.dirname(path), os.path.basename(path),
        as_attachment=True, download_name=real,
        mimetype="text/markdown; charset=utf-8",
    )


@bp.get("/api/notes/<name>")
def api_notes_read(name: str):
    try:
        return ok(note_service.read_note(name))
    except NoteError as exc:
        return _note_fail(exc, missing_status=404)


@bp.post("/api/notes")
def api_notes_create():
    payload = request.get_json(silent=True)
    if payload is None:
        return fail(E_BAD_REQUEST, "请求体必须是 JSON")
    try:
        data = note_service.create_note(payload.get("name", ""), payload.get("content"))
    except NoteError as exc:
        return _note_fail(exc)
    _index(data["name"])
    return ok(data, status=201)


@bp.put("/api/notes/<name>")
def api_notes_save(name: str):
    payload = request.get_json(silent=True)
    if payload is None:
        return fail(E_BAD_REQUEST, "请求体必须是 JSON")
    try:
        data = note_service.save_note(name, payload.get("content", ""))
    except NoteError as exc:
        return _note_fail(exc)
    _index(data["name"])
    return ok(data)


@bp.delete("/api/notes/<name>")
def api_notes_delete(name: str):
    try:
        data = note_service.delete_note(name)
    except NoteError as exc:
        return _note_fail(exc, missing_status=404)
    try:
        search_service.remove_note(data["name"])
    except Exception as exc:  # noqa: BLE001
        print(f"[search] remove_note 失败：{exc}")
    # 聊天记录随笔记一并删除（功能五约定，默认一并删除）
    ai_service.delete_chat_for_note(data["name"])
    return ok(data)
