"""进程级服务单例：路由蓝图与 app.py 共用，避免各模块各自 new。"""
from __future__ import annotations

from config import Config
from services import AIService, GitService, NoteService
from services.search_service import SearchService

note_service = NoteService(Config.NOTEBOOKS_DIR)
search_service = SearchService(Config.NOTEBOOKS_DIR, Config.SEARCH_INDEX_DIR)
ai_service = AIService(
    base_url=Config.AI_BASE_URL,
    api_key=Config.AI_API_KEY,
    model=Config.AI_MODEL,
    timeout=Config.AI_TIMEOUT,
)
git_service = GitService(Config.NOTEBOOKS_DIR, branch=Config.GIT_BRANCH)
