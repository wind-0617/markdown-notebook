"""Markdown 可执行笔记工具 —— Flask 应用入口。

启动：
    cd backend
    pip install -r requirements.txt
    python app.py
然后浏览器访问 http://127.0.0.1:5000

路由总览（详见 docs/API文档.md）：
    GET  /                     主页面（静态前端）
    GET  /api/health           健康检查
    POST /api/render           Markdown -> HTML
    POST /api/parse            提取代码块与交互参数
    POST /api/execute          执行代码块（可携带交互参数值）
    GET  /api/notes            笔记列表
    GET  /api/notes/<name>     读取笔记
    POST /api/notes            新建笔记
    PUT  /api/notes/<name>     保存笔记
    DELETE /api/notes/<name>   删除笔记
    POST /api/ai/chat          AI 助手对话
    GET  /api/git/status       Git 状态（阶段三）
    POST /api/git/init|commit|push|pull
"""
from __future__ import annotations

import os
import sys

# 若存在项目内依赖目录（pip install --target .deps -r requirements.txt）
# 且当前解释器缺 flask，则加入搜索路径，实现“克隆即用”（NFR-06）。
# 注意顺序：只在 flask 不可导入时才注入，避免 .deps 遮蔽 venv/系统里的更新版本。
_DEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deps")
if os.path.isdir(_DEPS):
    try:
        import flask  # noqa: F401
    except ImportError:
        if _DEPS not in sys.path:
            sys.path.insert(0, _DEPS)

from flask import Flask, jsonify, request, send_from_directory

try:  # flask-cors 可选：同源部署（本项目的默认方式）无需它
    from flask_cors import CORS
except ImportError:  # pragma: no cover
    CORS = None

from config import Config
from executors import get_executor, supported_languages
from parsers.markdown_parser import extract_code_blocks, render_html
from parsers.param_parser import build_executable_code
from services import AIService, GitError, GitService, NoteError, NoteService

app = Flask(__name__, static_folder=None)
app.config.from_object(Config)
if CORS is not None:
    CORS(app)

# ---- 服务实例（进程内单例） ------------------------------------------
note_service = NoteService(app.config["NOTEBOOKS_DIR"])
ai_service = AIService(
    base_url=app.config["AI_BASE_URL"],
    api_key=app.config["AI_API_KEY"],
    model=app.config["AI_MODEL"],
    timeout=app.config["AI_TIMEOUT"],
)
git_service = GitService(app.config["NOTEBOOKS_DIR"], branch=app.config["GIT_BRANCH"])


# ---- 静态前端 ---------------------------------------------------------
CDN_BASE = "https://cdn.jsdelivr.net"
_VENDOR_MARKER = os.path.join("vendor", "npm", "marked@12.0.0", "marked.min.js")


def _asset_base() -> str:
    """前端 CDN 依赖的基址：打包/离线（存在 vendor/ 镜像）时切换到 /vendor。

    ASSET_MODE：auto（默认，检测 vendor 目录）| local（强制 /vendor）| cdn。
    """
    mode = app.config.get("ASSET_MODE", "auto")
    if mode == "cdn":
        return CDN_BASE
    if mode == "local":
        return "/vendor"
    marker = os.path.join(app.config["FRONTEND_DIR"], *_VENDOR_MARKER.split(os.sep))
    return "/vendor" if os.path.isfile(marker) else CDN_BASE


def _index_html() -> str:
    """读取 index.html 并把 __ASSET_BASE__ 占位符替换为实际基址。"""
    path = os.path.join(app.config["FRONTEND_DIR"], "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().replace("__ASSET_BASE__", _asset_base())


@app.get("/")
def index():
    return _index_html()


@app.get("/<path:asset>")
def frontend_assets(asset: str):
    """托管 frontend/ 下的 css、js、vendor 等静态资源。"""
    return send_from_directory(app.config["FRONTEND_DIR"], asset)


# ---- API：基础 --------------------------------------------------------
@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "version": "0.2.0",
            "frozen": app.config.get("FROZEN", False),
            "asset_base": _asset_base(),
            "notebooks_dir": app.config["NOTEBOOKS_DIR"],
            "executor_mode": app.config["EXECUTOR_MODE"],
            "languages": supported_languages(),
            "ai_enabled": ai_service.enabled,
        }
    )


@app.post("/api/render")
def api_render():
    text = (request.get_json(silent=True) or {}).get("markdown", "")
    return jsonify({"html": render_html(text)})


@app.post("/api/parse")
def api_parse():
    text = (request.get_json(silent=True) or {}).get("markdown", "")
    blocks = extract_code_blocks(text)
    return jsonify({"blocks": [b.to_dict() for b in blocks]})


# ---- API：代码执行（FR-03 / FR-08） ------------------------------------
@app.post("/api/execute")
def api_execute():
    payload = request.get_json(silent=True) or {}
    language = (payload.get("language") or "python").strip().lower()
    code = payload.get("code") or ""
    params = payload.get("params") or {}          # {name: value} 交互参数
    timeout = payload.get("timeout")

    executor = get_executor(language)
    if executor is None:
        return jsonify({"error": f"暂不支持语言：{language}", "languages": supported_languages()}), 400

    if params:
        code = build_executable_code(language, code, params)

    result = executor.run(
        code,
        timeout=timeout,
        mode=app.config["EXECUTOR_MODE"],
        docker_image=app.config["DOCKER_SANDBOX_IMAGE"],
        memory_limit=app.config["DOCKER_MEMORY_LIMIT"],
        cpu_limit=app.config["DOCKER_CPU_LIMIT"],
    )
    return jsonify(result.to_dict())


# ---- API：笔记管理（FR-05） --------------------------------------------
@app.get("/api/notes")
def api_notes_list():
    return jsonify({"notes": note_service.list_notes()})


@app.get("/api/notes/<name>")
def api_notes_read(name: str):
    try:
        return jsonify(note_service.read_note(name))
    except NoteError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/notes")
def api_notes_create():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(note_service.create_note(payload.get("name", ""), payload.get("content")))
    except NoteError as exc:
        return jsonify({"error": str(exc)}), 400


@app.put("/api/notes/<name>")
def api_notes_save(name: str):
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(note_service.save_note(name, payload.get("content", "")))
    except NoteError as exc:
        return jsonify({"error": str(exc)}), 400


@app.delete("/api/notes/<name>")
def api_notes_delete(name: str):
    try:
        return jsonify(note_service.delete_note(name))
    except NoteError as exc:
        return jsonify({"error": str(exc)}), 400


# ---- API：AI 助手（FR-11，阶段三） --------------------------------------
@app.post("/api/ai/chat")
def api_ai_chat():
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages") or []
    if not messages and payload.get("prompt"):
        messages = [{"role": "user", "content": payload["prompt"]}]
    # ai: {base_url, model, api_key} —— 浏览器端配置覆盖 env 默认值（仅本机转发）
    result = ai_service.chat(messages, context=payload.get("context", ""),
                             overrides=payload.get("ai"))
    status = 200 if result.get("ok") else 503
    return jsonify(result), status


# ---- API：Git 同步（FR-12，阶段三） --------------------------------------
@app.get("/api/git/status")
def api_git_status():
    try:
        return jsonify(git_service.status())
    except GitError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/git/init")
def api_git_init():
    try:
        return jsonify(git_service.init_repo())
    except GitError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/git/commit")
def api_git_commit():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(git_service.commit(payload.get("message", "")))
    except GitError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/git/push")
def api_git_push():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(git_service.push(payload.get("remote", "origin")))
    except GitError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/git/pull")
def api_git_pull():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(git_service.pull(payload.get("remote", "origin")))
    except GitError as exc:
        return jsonify({"error": str(exc)}), 400


# ---- 兜底错误处理 -------------------------------------------------------
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "接口不存在"}), 404
    return _index_html()


@app.errorhandler(500)
def server_error(exc):
    return jsonify({"error": f"服务器内部错误：{exc}"}), 500


# ---- 启动入口 -----------------------------------------------------------
def _startup_banner(url: str) -> None:
    mode = app.config["EXECUTOR_MODE"]
    asset = "本地离线（vendor/）" if _asset_base() == "/vendor" else "CDN（需联网）"
    print("=" * 58)
    print("  📓 Markdown 可执行笔记工具")
    print(f"  地址      : {url}")
    print(f"  笔记目录  : {app.config['NOTEBOOKS_DIR']}")
    print(f"  代码执行  : {mode}" + ("（本机环境，勿运行未知来源笔记）" if mode == "local" else "（Docker 沙箱）"))
    print(f"  前端资源  : {asset}")
    print("  关闭此窗口即停止服务；数据均为标准 .md，可直接拷贝迁移。")
    print("=" * 58)


if __name__ == "__main__":
    host, port = app.config["HOST"], app.config["PORT"]
    url = f"http://{host}:{port}"

    if app.config.get("FROZEN"):
        _startup_banner(url)
        # 打包版双击运行时自动开浏览器；NO_BROWSER=1 或 run.ps1 自行打开时禁用
        if os.environ.get("NO_BROWSER", "") != "1":
            import threading
            import webbrowser
            threading.Timer(1.2, webbrowser.open, [url]).start()

    app.run(
        host=host,
        port=port,
        debug=app.config["DEBUG"],
        # 冻结环境禁用 reloader：否则 reloader 会再次拉起 exe 自身
        use_reloader=app.config["DEBUG"] and not app.config.get("FROZEN"),
    )
