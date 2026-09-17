"""全文检索 API（九.3）：查询 + 索引重建。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import E_BAD_REQUEST, E_SEARCH_ERROR, ok, fail
from config import Config
from deps import search_service

bp = Blueprint("search", __name__)


@bp.get("/api/search")
def api_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return fail(E_BAD_REQUEST, "缺少查询词 q")
    if len(query) > 200:
        return fail(E_BAD_REQUEST, "查询词过长（≤200 字符）")
    try:
        results = search_service.search(query, limit=Config.SEARCH_MAX_RESULTS)
    except Exception as exc:  # noqa: BLE001
        return fail(E_SEARCH_ERROR, f"检索失败：{exc}", status=500)
    return ok({"query": query, "results": results, "total": len(results)})


@bp.post("/api/search/rebuild")
def api_search_rebuild():
    try:
        count = search_service.rebuild()
    except Exception as exc:  # noqa: BLE001
        return fail(E_SEARCH_ERROR, f"索引重建失败：{exc}", status=500)
    return ok({"indexed": count})
