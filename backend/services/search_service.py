"""全文检索服务（指令文档·九.3）：Whoosh 实现，覆盖 文件名 / 一级标题 / 正文。

中文适配：Whoosh 标准分词不切 CJK（整句成为一个 token）。这里用
**unigram + bigram 双字节滑动窗口** 分析器，索引与查询共用同一实现，
可稳定支持「笔记」「可执行」「python」等混合查询，并配 OrGroup 宽松召回。

索引目录必须可写（打包态已指向 exe 同级）；笔记 新建/保存/删除 时增量维护，
启动后首次查询若索引缺失则自动全量重建。
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone

from whoosh.analysis import Token, Tokenizer
from whoosh.fields import DATETIME, ID, Schema, TEXT
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import MultifieldParser, OrGroup

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WORD = re.compile(r"[A-Za-z0-9_]+")
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class CjkBigramTokenizer(Tokenizer):
    """CJK 连续段产 unigram+bigram；拉丁/数字按词小写。

    Whoosh 会以 (value, mode=...) 调用分析器，也偶而调用 reset()/clone()。
    """

    def reset(self) -> None:  # 无状态实现，接口占位以满足 Whoosh 约定
        pass

    def __call__(self, value, mode="default", positions=True, keeplist=False, **kw):
        # Whoosh 分析器协议：可能带 mode/positions/boosts/keeplist 等参数，一律接受。
        # POSITIONS 格式要求每个 token 具备 .pos（词序，1 起）与 mode。
        pos = 0
        i, n = 0, len(value)
        while i < n:
            ch = value[i]
            if _CJK.match(ch):
                j = i
                while j < n and _CJK.match(value[j]):
                    j += 1
                run = value[i:j]
                for k in range(len(run)):
                    pos += 1
                    yield self._token(run[k], i + k, i + k + 1, pos)
                    if k + 1 < len(run):
                        pos += 1
                        yield self._token(run[k:k + 2], i + k, i + k + 2, pos)
                i = j
                continue
            m = _WORD.match(value, i)
            if m:
                pos += 1
                yield self._token(m.group(0).lower(), m.start(), m.end(), pos)
                i = m.end()
            else:
                i += 1

    @staticmethod
    def _token(text, startpos, endpos, pos):
        tok = Token(text=text, startpos=startpos, endpos=endpos)
        tok.mode = "word"
        tok.pos = pos
        return tok


# 可调用分析器：whoosh 接受任意 (text)->tokens 生成器；本实现已内置小写化
ANALYZER = CjkBigramTokenizer()

_SCHEMA = Schema(
    name=ID(stored=True, unique=True),
    title=TEXT(analyzer=ANALYZER, stored=True),
    content=TEXT(analyzer=ANALYZER),
    modified=DATETIME(stored=True, sortable=True),
)


class SearchError(Exception):
    pass


class SearchService:
    def __init__(self, notes_dir: str, index_dir: str) -> None:
        self.notes_dir = os.path.abspath(notes_dir)
        self.index_dir = os.path.abspath(index_dir)
        self._lock = threading.Lock()
        self._ix = None

    # ---- 索引生命周期 -------------------------------------------------
    def _open(self):
        if self._ix is not None:
            return self._ix
        os.makedirs(self.index_dir, exist_ok=True)
        try:
            if exists_in(self.index_dir):
                self._ix = open_dir(self.index_dir)
            else:
                self._ix = create_in(self.index_dir, _SCHEMA)
                self.rebuild()
        except Exception:  # 索引损坏/版本不符：推倒重建
            self._ix = create_in(self.index_dir, _SCHEMA)
            self.rebuild()
        return self._ix

    def _file_meta(self, name: str):
        path = os.path.join(self.notes_dir, name)
        stat = os.stat(path)
        return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

    def index_note(self, name: str) -> None:
        """单篇增量更新（保存/新建后调用）。"""
        path = os.path.join(self.notes_dir, name)
        if not os.path.isfile(path):
            self.remove_note(name)
            return
        try:
            content = open(path, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            return
        ix = self._open()          # 先取索引（可能触发重建），再进写锁，避免重入死锁
        with self._lock, ix.writer() as w:
            w.update_document(
                name=name,
                title=_title_of(name, content),
                content=content,
                modified=self._file_meta(name),
            )

    def remove_note(self, name: str) -> None:
        ix = self._open()
        with self._lock, ix.writer() as w:
            w.delete_by_term("name", name)

    def rebuild(self) -> int:
        """全量重建索引，返回收录篇数。"""
        count = 0
        os.makedirs(self.index_dir, exist_ok=True)
        ix = create_in(self.index_dir, _SCHEMA)
        self._ix = ix
        with self._lock, ix.writer() as w:
            for fname in sorted(os.listdir(self.notes_dir)):
                if not fname.lower().endswith(".md"):
                    continue
                path = os.path.join(self.notes_dir, fname)
                if not os.path.isfile(path):
                    continue
                content = open(path, "r", encoding="utf-8", errors="replace").read()
                stat = os.stat(path)
                w.add_document(
                    name=fname,
                    title=_title_of(fname, content),
                    content=content,
                    modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
                count += 1
        return count

    # ---- 查询 ---------------------------------------------------------
    def search(self, query: str, limit: int = 30) -> list[dict]:
        query = (query or "").strip()
        if not query:
            return []
        ix = self._open()
        parser = MultifieldParser(["title", "content", "name"], ix.schema, group=OrGroup)
        q = parser.parse(query)
        # OrGroup 使所有 token 命中其一即召回（召回优先）；展示按修改时间倒序更直观
        with ix.searcher() as s:
            results = s.search(q, limit=max(limit, 1) * 3, sortedby="modified", reverse=True)
            out: list[dict] = []
            terms = _query_terms(query)
            for hit in results:
                if len(out) >= limit:
                    break
                name = hit["name"]
                content = ""
                try:
                    path = os.path.join(self.notes_dir, name)
                    if os.path.isfile(path):
                        content = open(path, "r", encoding="utf-8", errors="replace").read()
                except OSError:
                    pass
                modified = hit["modified"]
                out.append(
                    {
                        "name": name,
                        "title": hit["title"] or name,
                        "snippet": _snippet(content or str(hit["title"] or ""), terms),
                        "modified": int(modified.timestamp()) if modified else 0,
                        "score": round(float(hit.score or 0), 3),
                    }
                )
            return out


# ----------------------------------------------------------------------
def _title_of(name: str, content: str) -> str:
    m = _H1.search(content or "")
    return m.group(1).strip() if m else os.path.splitext(name)[0]


def _query_terms(query: str) -> list[str]:
    toks = [t.text for t in ANALYZER(query)]
    return list(dict.fromkeys(toks))[:12]


def _snippet(content: str, terms: list[str], window: int = 84) -> str:
    """截取首个命中词附近窗口并单遍高亮（先转义，长词优先，避免嵌套标签）。"""
    if not content:
        return ""
    low = content.lower()
    pos = -1
    for t in terms:
        p = low.find(t.lower())
        if p != -1 and (pos == -1 or p < pos):
            pos = p
    if pos == -1:
        pos = 0
    start = max(0, pos - window // 2)
    frag = content[start:start + window * 2]
    if start > 0:
        frag = "…" + frag
    if start + window * 2 < len(content):
        frag += "…"
    frag = frag.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    uniq = sorted({t for t in terms if t and not t.isdigit()}, key=len, reverse=True)
    if uniq:
        pattern = "|".join(
            re.escape(t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            for t in uniq
        )
        frag = re.sub(
            f"({pattern})", lambda m: f"<u>{m.group(1)}</u>", frag, flags=re.IGNORECASE
        )
    return frag
