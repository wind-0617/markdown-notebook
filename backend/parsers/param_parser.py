"""交互参数解析器（FR-07 / FR-08）。

在代码块内用注释声明控件，执行前把声明行替换为变量赋值：

  Python:  # @param n 样本量 slider min=1 max=100 step=1 default=10
  JS:      // @param base 底数 number min=0 max=10 default=2
  Shell:   # @param name 名字 text default=world
  通用:    select 类型用 options=a,b,c 声明候选值
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# @param 声明行：<注释符> @param <变量名> [标签] <控件类型> <k=v 对...>
_PARAM_RE = re.compile(
    r"^\s*(?:#|//)\s*@param\s+"
    r"(?P<name>\w+)\s+"
    r'(?:"(?P<label1>[^"]*)"|(?P<label>\S*))\s*'
    r"(?P<kind>\w+)?\s*"
    r"(?P<opts>(?:\w+=\S*\s*)*)$",
)

_KV_RE = re.compile(r"(\w+)=(\S+)")

VALID_KINDS = {"slider", "number", "select", "text", "checkbox"}

_COMMENT_PREFIX = {
    "python": "#",
    "shell": "#",
    "javascript": "//",
}


@dataclass
class ParamSpec:
    """一个交互控件的定义。"""

    name: str
    label: str = ""
    kind: str = "number"            # slider | number | select | text | checkbox
    min: float | None = None
    max: float | None = None
    step: float | None = None
    default: Any = None
    options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label or self.name,
            "kind": self.kind,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "default": self.default,
            "options": self.options,
        }


def parse_params(language: str, code: str) -> list[ParamSpec]:
    """扫描代码块中的 @param 注释行，返回控件定义列表。"""
    params: list[ParamSpec] = []
    for line in code.splitlines():
        spec = parse_param_line(line)
        if spec is not None:
            params.append(spec)
    return params


def parse_param_line(line: str) -> ParamSpec | None:
    m = _PARAM_RE.match(line)
    if not m:
        return None
    name = m.group("name")
    label = m.group("label1") or m.group("label") or name
    kind = (m.group("kind") or "number").lower()
    if kind not in VALID_KINDS:
        kind = "number"

    kv = dict(_KV_RE.findall(m.group("opts") or ""))
    spec = ParamSpec(name=name, label=label, kind=kind)
    spec.min = _as_float(kv.get("min"))
    spec.max = _as_float(kv.get("max"))
    spec.step = _as_float(kv.get("step"))
    if "options" in kv:
        spec.options = kv["options"].split(",")
    default = kv.get("default")
    spec.default = _coerce(kind, default, spec)
    return spec


def strip_param_lines(language: str, code: str) -> str:
    """移除全部 @param 声明行，返回“纯代码”。"""
    kept = [ln for ln in code.splitlines() if parse_param_line(ln) is None]
    return "\n".join(kept)


def build_executable_code(language: str, code: str, values: dict[str, Any]) -> str:
    """生成实际执行的代码：删掉 @param 声明行，并在文件头部注入参数赋值。"""
    pure = strip_param_lines(language, code)
    prefix = _COMMENT_PREFIX.get(language, "#")
    lines = [f"{prefix} ---- 交互参数（自动生成） ----"]
    for key, value in values.items():
        if not re.fullmatch(r"\w+", key):
            continue
        lines.append(f"{key} = {_literal(language, value)}")
    return "\n".join(lines) + "\n\n" + pure


# ------------------------------------------------------------------
def _as_float(v: str | None) -> float | None:
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def _coerce(kind: str, raw: str | None, spec: ParamSpec) -> Any:
    if raw is None:
        if kind == "checkbox":
            return False
        if kind == "select" and spec.options:
            return spec.options[0]
        return 0
    if kind in ("slider", "number"):
        val = _as_float(raw)
        return val if val is not None else 0
    if kind == "checkbox":
        return raw.lower() in ("1", "true", "yes", "on")
    return raw


def _literal(language: str, value: Any) -> str:
    """把参数值转成对应语言的字面量。"""
    if language == "javascript":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"
    # Python / Shell 共用 repr 风格（shell 里数值同样成立）
    if isinstance(value, (int, float, bool)) or value is None:
        return repr(value)
    return repr(str(value))
