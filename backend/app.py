"""Markdown 可执行笔记工具 —— Flask API 入口（v0.3，前后端分离）

职责边界（指令文档·二/五）：
  • 只提供 /api JSON 接口，不渲染页面、不做业务前端逻辑；
  • 唯一例外：把 Vite 构建产物 frontend/dist 作为**纯静态文件**托管——
    这是 exe 双击即用交付形态的内置静态服务器（等价 Nginx 的角色），
    不是服务端渲染；开发态由 Vite dev server + /api 代理承担。

开发态两种跑法：
  1) 全栈一键：  run.ps1 / run.sh / run.cmd（自动 npm build 后由本服务托管）
  2) 分离开发：  终端A python app.py ；终端B cd frontend && npm run dev
                 （Vite 代理 /api → 127.0.0.1:5000，浏览器访问 5173）

API 一览见 docs/API文档.md；全部响应遵循统一信封：
  {"success": bool, "data": ..., "error": {"code","message"}|null}
"""
from __future__ import annotations

import os
import sys

# 若存在项目内依赖目录且当前解释器缺 flask，则加入搜索路径（NFR-06 克隆即用）。
# 只在 flask 不可导入时注入，避免 .deps 遮蔽 venv/系统里的更新版本。
_DEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deps")
if os.path.isdir(_DEPS):
    try:
        import flask  # noqa: F401
    except ImportError:
        if _DEPS not in sys.path:
            sys.path.insert(0, _DEPS)

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import NotFound

from api_response import E_INTERNAL, E_NOT_FOUND, fail
from config import Config
from routes import register_blueprints


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    try:  # flask-cors 可选；默认同源。仅显式给出白名单才开启跨域（禁止长期 *）
        from flask_cors import CORS
        if Config.CORS_ORIGINS:
            CORS(app, origins=Config.CORS_ORIGINS)
    except ImportError:  # pragma: no cover
        pass

    register_blueprints(app)
    _mount_static(app)

    @app.errorhandler(NotFound)
    def _not_found(_):
        if request.path.startswith("/api/"):
            return fail(E_NOT_FOUND, f"接口不存在：{request.path}", status=404)
        return fail(E_NOT_FOUND, "资源不存在", status=404)

    @app.errorhandler(Exception)
    def _server_error(exc):  # 500 也走统一信封，前端 Toast 才有稳定形状
        if request.path.startswith("/api/"):
            app.logger.exception("API 内部错误")
            return fail(E_INTERNAL, f"服务器内部错误：{exc}", status=500)
        raise exc

    return app


def _mount_static(app: Flask) -> None:
    """托管 Vite 构建产物（静态文件服务，非页面渲染，见模块头说明）。"""

    def dist_ready() -> bool:
        return os.path.isfile(os.path.join(app.config["FRONTEND_DIST_DIR"], "index.html"))

    @app.get("/")
    def index():
        if not dist_ready():
            return fail(
                E_NOT_FOUND,
                "前端未构建：开发请运行 `cd frontend && npm install && npm run dev`"
                "（Vite 代理模式，访问 5173 端口）；或 `npm run build` 后由本服务托管。",
                status=404,
            )
        return send_from_directory(app.config["FRONTEND_DIST_DIR"], "index.html")

    @app.get("/<path:asset>")
    def static_asset(asset: str):
        if not dist_ready():
            return fail(E_NOT_FOUND, "前端未构建", status=404)
        return send_from_directory(app.config["FRONTEND_DIST_DIR"], asset)


app = create_app()


# ---- 启动入口 -----------------------------------------------------------
def _startup_banner(url: str) -> None:
    mode = Config.EXECUTOR_MODE
    print("=" * 58)
    print("  📓 Markdown 可执行笔记工具")
    print(f"  地址      : {url}")
    print(f"  笔记目录  : {Config.NOTEBOOKS_DIR}")
    print(f"  代码执行  : {mode}" + ("（本机环境，勿运行未知来源笔记）" if mode == "local" else "（Docker 沙箱）"))
    print(f"  前端      : {'内置 dist（离线可用）' if os.path.isfile(os.path.join(Config.FRONTEND_DIST_DIR, 'index.html')) else '未构建——仅 API 模式，请配合 vite dev'}")
    print("  关闭此窗口即停止服务；数据均为标准 .md，可直接拷贝迁移。")
    print("=" * 58)


if __name__ == "__main__":
    host, port = Config.HOST, Config.PORT
    url = f"http://{host}:{port}"

    if Config.FROZEN:
        _startup_banner(url)
        # 打包版双击运行时自动开浏览器；NO_BROWSER=1 可禁用
        if os.environ.get("NO_BROWSER", "") != "1":
            import threading
            import webbrowser
            threading.Timer(1.2, webbrowser.open, [url]).start()

    app.run(
        host=host,
        port=port,
        debug=Config.DEBUG,
        # 冻结环境禁用 reloader：否则 reloader 会再次拉起 exe 自身
        use_reloader=Config.DEBUG and not Config.FROZEN,
    )
