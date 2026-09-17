"""Git 同步 API（FR-12）。"""
from __future__ import annotations

from flask import Blueprint, request

from api_response import E_GIT_ERROR, ok, fail
from deps import git_service
from services import GitError

bp = Blueprint("git", __name__)


def _git(call):
    try:
        return ok(call())
    except GitError as exc:
        return fail(E_GIT_ERROR, str(exc))


@bp.get("/api/git/status")
def api_git_status():
    return _git(git_service.status)


@bp.post("/api/git/init")
def api_git_init():
    return _git(git_service.init_repo)


@bp.post("/api/git/commit")
def api_git_commit():
    payload = request.get_json(silent=True) or {}
    return _git(lambda: git_service.commit(payload.get("message", "")))


@bp.post("/api/git/push")
def api_git_push():
    payload = request.get_json(silent=True) or {}
    return _git(lambda: git_service.push(payload.get("remote", "origin")))


@bp.post("/api/git/pull")
def api_git_pull():
    payload = request.get_json(silent=True) or {}
    return _git(lambda: git_service.pull(payload.get("remote", "origin")))
