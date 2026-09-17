"""笔记 CRUD API（FR-05）。所有写操作后同步全文检索索引（九.3）。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import (
    E_BAD_REQUEST,
    E_NAME_INVALID,
    E_NOT_FOUND,
    E_NOTE_EXISTS,
    ok,
    fail,
)
from deps import note_service, search_service
from services import NoteError

bp = Blueprint("notes", __name__)


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
    return ok(data)
