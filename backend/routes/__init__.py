"""API 路由包：register_blueprints 统一挂载。后端只做 JSON，不渲染页面。"""
from __future__ import annotations

from flask import Blueprint

from . import ai_routes, execute_routes, git_routes, note_routes, render_routes, search_routes, system_routes

_BLUEPRINTS = (
    system_routes.bp,
    render_routes.bp,
    execute_routes.bp,
    note_routes.bp,
    search_routes.bp,
    ai_routes.bp,
    git_routes.bp,
)


def register_blueprints(app) -> None:
    for bp in _BLUEPRINTS:
        app.register_blueprint(bp)
