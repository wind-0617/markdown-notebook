"""Markdown 解析器：渲染 HTML + 提取可执行代码块。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .param_parser import ParamSpec, parse_params

# 围栏代码块：```lang\n...\n```（兼容 ~~~）
_FENCE_RE = re.compile(
    r"^(?: {0,3})(?P<fence>```+|~~~+)\s*(?P<lang>[\w+-]*)[^\n]*\n"
    r"(?P<body>.*?)"
    r"^(?: {0,3})(?P=fence)\s*$",
    re.MULTILINE | re.DOTALL,
)

# 可执行的语言（与 executors 注册表保持一致，可按需扩展）
RUNNABLE_LANGUAGES = {"python", "javascript", "js", "shell", "bash", "sh"}

_LANG_ALIAS = {"js": "javascript", "bash": "shell", "sh": "shell"}

_MD_EXTENSIONS = ["fenced_code", "tables", "toc", "codehilite", "nl2br"]


@dataclass
class CodeBlock:
    """笔记中的一个代码块。"""

    index: int
    language: str          # 归一化后的语言名
    raw_language: str      # 围栏上写的原始语言
    code: str
    start_line: int        # 在文档中的行号（1 起）
    params: list[ParamSpec]

    @property
    def runnable(self) -> bool:
        return self.language in RUNNABLE_LANGUAGES

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "language": self.language,
            "raw_language": self.raw_language,
            "code": self.code,
            "start_line": self.start_line,
            "runnable": self.runnable,
            "params": [p.to_dict() for p in self.params],
        }


def render_html(text: str) -> str:
    """Markdown -> HTML（FR-02 服务端渲染入口；前端另用 marked 做即时预览）。

    第三方库延迟导入：未安装 Markdown 包时，仅本函数不可用，
    代码块提取等其他能力不受影响。
    """
    try:
        import markdown as md
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "服务端渲染需要 Markdown 库：pip install -r backend/requirements.txt"
        ) from exc
    return md.markdown(
        text,
        extensions=_MD_EXTENSIONS,
        output_format="html5",
    )


def extract_code_blocks(text: str) -> list[CodeBlock]:
    """提取全部围栏代码块，并解析其中的交互参数（FR-07）。"""
    blocks: list[CodeBlock] = []
    for i, m in enumerate(_FENCE_RE.finditer(text)):
        raw_lang = (m.group("lang") or "").strip().lower()
        lang = _LANG_ALIAS.get(raw_lang, raw_lang)
        code = m.group("body")
        start_line = text.count("\n", 0, m.start()) + 1
        blocks.append(
            CodeBlock(
                index=i,
                language=lang,
                raw_language=raw_lang,
                code=code,
                start_line=start_line,
                params=parse_params(lang, code),
            )
        )
    return blocks


def find_block_at_line(blocks: list[CodeBlock], line: int) -> Optional[CodeBlock]:
    """找光标处（或其后）最近的代码块，用于 Shift+Enter 执行。"""
    for block in blocks:
        if block.start_line >= line - 1 and block.runnable:
            return block
    for block in reversed(blocks):
        if block.start_line <= line and block.runnable:
            return block
    return None
