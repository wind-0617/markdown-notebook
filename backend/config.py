"""全局配置：全部支持环境变量覆盖，便于本地开发与 Docker 部署共用。

冻结（PyInstaller 打包）感知：
  - 只读资源（frontend/、vendor 资产）从 sys._MEIPASS 解包目录解析
  - 可写数据（notebooks/）放在 exe 同级目录，升级/重打包不丢笔记
"""
from __future__ import annotations

import os
import sys

FROZEN = getattr(sys, "frozen", False)                    # PyInstaller 单文件模式
BUNDLE_DIR = getattr(sys, "_MEIPASS", "")                 # 只读资源根（打包后）
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else ""

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)               # 开发态=仓库根；打包态无意义，勿用


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    """Flask 应用配置。"""

    FROZEN = FROZEN

    SECRET_KEY = os.environ.get("SECRET_KEY", "markdown-notebook-dev")

    # 服务监听
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = _int("PORT", 5000)
    # 打包版强制单进程（Werkzeug reloader 在冻结环境会自启 exe）
    DEBUG = os.environ.get("FLASK_DEBUG", "0" if FROZEN else "1") == "1"

    # 目录
    FRONTEND_DIR = (
        os.path.join(BUNDLE_DIR, "frontend") if FROZEN
        else os.path.join(PROJECT_ROOT, "frontend")
    )
    NOTEBOOKS_DIR = os.environ.get(
        "NOTEBOOKS_DIR",
        os.path.join(APP_DIR, "notebooks") if FROZEN
        else os.path.join(BACKEND_DIR, "notebooks"),
    )
    # 前端资源加载：auto=检测到 frontend/vendor 则离线本地化，否则走 CDN
    ASSET_MODE = os.environ.get("ASSET_MODE", "auto").lower()  # auto | local | cdn

    # 代码执行（NFR-01 安全 / NFR-02 性能）
    #   local  : 本机 subprocess（开发默认）
    #   docker : Docker 沙箱容器（生产建议）
    EXECUTOR_MODE = os.environ.get("EXECUTOR_MODE", "local").lower()
    DEFAULT_TIMEOUT = _int("EXEC_TIMEOUT", 30)          # 秒，文档 NFR-02
    MAX_TIMEOUT = _int("EXEC_MAX_TIMEOUT", 120)         # 上限，防止占用过久
    DOCKER_SANDBOX_IMAGE = os.environ.get(
        "DOCKER_SANDBOX_IMAGE", "markdown-notebook-sandbox:latest"
    )
    DOCKER_MEMORY_LIMIT = os.environ.get("DOCKER_MEMORY_LIMIT", "256m")
    DOCKER_CPU_LIMIT = os.environ.get("DOCKER_CPU_LIMIT", "0.5")

    # AI 助手（OpenAI 兼容 API，FR-11；支持 DeepSeek / GPT / Ollama 等）
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
    AI_TIMEOUT = _int("AI_TIMEOUT", 60)

    # Git 同步（FR-12）
    GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")
