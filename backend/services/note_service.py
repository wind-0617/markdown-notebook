"""笔记管理服务（FR-05）：notebooks 目录下的 .md 文件 CRUD。

所有文件名都经过安全校验，禁止路径穿越（NFR-01）。
"""
from __future__ import annotations

import os
import re
import time

_NAME_RE = re.compile(r"^[\w\u4e00-\u9fff .()\-]{1,96}\.md$")


def _remove_retry(path: str, attempts: int = 4, delay: float = 0.15) -> None:
    """Windows 上刚读/改名过的文件可能被杀软短暂占用，重试后仍失败才抛。"""
    last: OSError | None = None
    for _ in range(attempts):
        try:
            os.remove(path)
            return
        except PermissionError as exc:
            last = exc
            time.sleep(delay)
    assert last is not None
    raise last


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
        _remove_retry(path)
        return {"name": real, "deleted": True}

    def rename_note(self, old_name: str, new_name: str) -> dict:
        """重命名（功能一）。new_name 可省略 .md 后缀；校验后原子改名。"""
        real_old, path_old = self._safe_path(old_name)
        candidate = (new_name or "").strip()
        if candidate and not candidate.lower().endswith(".md"):
            candidate += ".md"
        real_new, path_new = self._safe_path(candidate)
        if not os.path.isfile(path_old):
            raise NoteError(f"笔记不存在：{real_old}")
        if real_old == real_new:
            raise NoteError("新旧文件名相同，无需重命名")
        if os.path.exists(path_new):
            raise NoteError(f"笔记已存在：{real_new}")
        os.replace(path_old, path_new)
        return {"old_name": real_old, "name": real_new, "renamed": True}

    def prepare_export(self, name: str) -> tuple[str, str]:
        """导出（功能三）前置：返回 (真实文件名, 绝对路径) 供 send_from_directory。"""
        real, path = self._safe_path(name)
        if not os.path.isfile(path):
            raise NoteError(f"笔记不存在：{real}")
        return real, path

    # ------------------------------------------------------------------
    def _safe_path(self, name: str) -> tuple[str, str]:
        """返回 (净化后的文件名, 绝对路径)。响应必须回显净化名，避免误导客户端。

        严格化：显式拒绝含路径分隔符或 .. 的输入（安全·七），不再静默 basename
        把一个非法名悄悄变成另一个合法名——那会让「x/y」被存成 y.md，误导用户。
        """
        raw = (name or "").strip()
        if not raw:
            raise NoteError("文件名不能为空")
        if "/" in raw or "\\" in raw or ".." in raw:
            raise NoteError(
                "文件名不合法：不能包含路径分隔符 / \\ .. 或 : * ? \" < > | 等字符"
            )
        name = os.path.basename(raw)
        if not _NAME_RE.match(name):
            raise NoteError(
                "文件名不合法：仅允许中文、字母、数字、空格与 .()-_，且必须以 .md 结尾"
            )
        path = os.path.realpath(os.path.join(self.root, name))
        if not path.startswith(self.root + os.sep):
            raise NoteError("非法路径")
        return name, path
