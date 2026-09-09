"""笔记管理服务（FR-05）：notebooks 目录下的 .md 文件 CRUD。

所有文件名都经过安全校验，禁止路径穿越（NFR-01）。
"""
from __future__ import annotations

import os
import re

_NAME_RE = re.compile(r"^[\w\u4e00-\u9fff .()\-]{1,96}\.md$")


class NoteError(Exception):
    """笔记操作失败（携带 HTTP 状态码语义的消息）。"""


class NoteService:
    def __init__(self, root_dir: str) -> None:
        self.root = os.path.abspath(root_dir)
        os.makedirs(self.root, exist_ok=True)

    # ------------------------------------------------------------------
    def list_notes(self) -> list[dict]:
        items = []
        for name in sorted(os.listdir(self.root)):
            path = os.path.join(self.root, name)
            if os.path.isfile(path) and name.lower().endswith(".md"):
                stat = os.stat(path)
                items.append(
                    {
                        "name": name,
                        "size": stat.st_size,
                        "modified": int(stat.st_mtime),
                    }
                )
        return items

    def read_note(self, name: str) -> dict:
        real, path = self._safe_path(name)
        if not os.path.isfile(path):
            raise NoteError(f"笔记不存在：{real}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"name": real, "content": content}

    def save_note(self, name: str, content: str) -> dict:
        real, path = self._safe_path(name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"name": real, "saved": True, "size": len(content.encode("utf-8"))}

    def create_note(self, name: str, content: str = "") -> dict:
        real, path = self._safe_path(name)
        if os.path.exists(path):
            raise NoteError(f"笔记已存在：{real}")
        default = content or f"# {os.path.splitext(real)[0]}\n\n新建笔记...\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(default)
        return {"name": real, "created": True}

    def delete_note(self, name: str) -> dict:
        real, path = self._safe_path(name)
        if not os.path.isfile(path):
            raise NoteError(f"笔记不存在：{real}")
        os.remove(path)
        return {"name": real, "deleted": True}

    # ------------------------------------------------------------------
    def _safe_path(self, name: str) -> tuple[str, str]:
        """返回 (净化后的文件名, 绝对路径)。响应必须回显净化名，避免误导客户端。"""
        name = os.path.basename((name or "").strip())
        if not _NAME_RE.match(name):
            raise NoteError(
                "文件名不合法：仅允许中文、字母、数字、空格与 .()-_，且必须以 .md 结尾"
            )
        path = os.path.realpath(os.path.join(self.root, name))
        if not path.startswith(self.root + os.sep):
            raise NoteError("非法路径")
        return name, path
