"""渲染与解析 API。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import E_BAD_REQUEST, ok, fail
from parsers.markdown_parser import extract_code_blocks, render_html

bp = Blueprint("render", __name__)


@bp.post("/api/render")
def api_render():
    payload = request.get_json(silent=True)
    if payload is None:
        return fail(E_BAD_REQUEST, "请求体必须是 JSON")
    return ok({"html": render_html(payload.get("markdown", ""))})


@bp.post("/api/parse")
def api_parse():
    payload = request.get_json(silent=True)
    if payload is None:
        return fail(E_BAD_REQUEST, "请求体必须是 JSON")
    blocks = extract_code_blocks(payload.get("markdown", ""))
    return ok({"blocks": [b.to_dict() for b in blocks]})
