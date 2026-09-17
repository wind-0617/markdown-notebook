"""AI 助手服务（FR-11）：OpenAI 兼容 Chat Completions 封装 + 聊天记录持久化。

通过环境变量配置，可接 DeepSeek / OpenAI / Ollama 等任意兼容端点：
  AI_BASE_URL  例如 https://api.deepseek.com/v1 或 http://localhost:11434/v1
  AI_API_KEY   服务端密钥（Ollama 可留空）
  AI_MODEL     模型名，如 deepseek-chat / gpt-4o-mini / qwen2.5

未配置密钥时返回明确的“未启用”提示，前端据此引导用户配置。

聊天记录（功能五）：与笔记绑定，存 notebooks/<同名>.ai-chat.json，
随笔记删除而删除、随笔记重命名而迁移；本模块复用 note_service 的
文件名白名单，禁止路径穿越。
"""
from __future__ import annotations

import json
import os

try:
    import requests
except ImportError:  # pragma: no cover  未安装时 AI 功能降级为明确报错
    requests = None

from .note_service import NoteError, _NAME_RE

SYSTEM_PROMPT = (
    "你是 Markdown 可执行笔记工具内置的编程与写作助手。"
    "回答保持简洁，代码建议以 Markdown 围栏代码块给出，"
    "如适合在笔记中运行，优先给出 Python 代码。"
)

CHAT_SUFFIX = ".ai-chat.json"
MAX_CHAT_MESSAGES = 500          # 单笔记消息上限（防滥用撑爆文件）
MAX_CHAT_CONTENT = 50_000        # 单条消息内容上限（字节量级）


class AIResult(dict):
    """统一返回结构：{ok, reply | error}。"""


class AIService:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        notebooks_dir: str = "",
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.chat_root = os.path.abspath(notebooks_dir) if notebooks_dir else None

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model)

    # ------------------------------------------------------------------
    # 对话与连接测试
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        context: str = "",
        overrides: dict | None = None,
        timeout: int | None = None,
    ) -> AIResult:
        """一次对话。overrides 允许浏览器传入自己的配置（localStorage 保存），
        仅本机 backend 转发使用，不会写盘、不会回显。"""
        if requests is None:
            return AIResult(ok=False, error="未安装 requests，请先 pip install requests。")
        ov = {k: str(v).strip() for k, v in (overrides or {}).items() if v}
        base_url = (ov.get("base_url") or self.base_url).rstrip("/")
        api_key = ov.get("api_key") or self.api_key
        model = ov.get("model") or self.model

        if not base_url or not model:
            return AIResult(
                ok=False,
                not_configured=True,
                error="AI 服务未配置：请在 AI 助手面板右上角 ⚙️ 中填写服务地址与模型名"
                      "（也可用环境变量 AI_BASE_URL / AI_MODEL 配置默认值）。",
            )
        local = "localhost" in base_url or "127.0.0.1" in base_url
        if not api_key and not local:
            return AIResult(
                ok=False,
                not_configured=True,
                error="未配置 API Key，无法调用远端模型：请在 AI 助手面板右上角 ⚙️ 中填写。"
                      "（本地 Ollama 等无需 Key 的服务请使用 http://localhost:… 地址）",
            )

        payload_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context.strip():
            payload_messages.append(
                {"role": "system", "content": f"当前笔记内容（供参考）：\n{context[:12000]}"}
            )
        payload_messages.extend(
            {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:8000]}
            for m in messages[-20:]
        )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                json={"model": model, "messages": payload_messages},
                headers=headers,
                timeout=timeout or self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return AIResult(ok=True, reply=reply, model=model)
        except requests.RequestException as exc:
            return AIResult(ok=False, error=f"AI 接口调用失败：{exc}")
        except (KeyError, ValueError) as exc:
            return AIResult(ok=False, error=f"AI 响应格式异常：{exc}")

    def test_connection(self, overrides: dict | None = None) -> AIResult:
        """功能四：轻量连通性测试。发一条最短消息验证 地址/模型/Key 三件套。"""
        result = self.chat(
            [{"role": "user", "content": "连接测试，请仅回复：OK"}],
            overrides=overrides,
            timeout=20,
        )
        if result.get("ok"):
            return AIResult(ok=True, model=result.get("model"),
                            reply=result.get("reply", "")[:60])
        return result

    # ------------------------------------------------------------------
    # 聊天记录持久化（功能五）
    # ------------------------------------------------------------------
    def _chat_path(self, note_name: str) -> tuple[str, str]:
        """note「X.md」→ (真实笔记名, notebooks/X.ai-chat.json 绝对路径)。
        与 note_service._safe_path 同等严格：拒绝分隔符/..，不静默净化。"""
        if not self.chat_root:
            raise NoteError("聊天记录存储未启用")
        raw = (note_name or "").strip()
        if not raw or "/" in raw or "\\" in raw or ".." in raw:
            raise NoteError("文件名不合法：不能包含路径分隔符或 ..")
        if not _NAME_RE.match(raw):
            raise NoteError("文件名不合法：仅允许中文、字母、数字、空格与 .()-_，且必须以 .md 结尾")
        stem = raw[:-3] if raw.lower().endswith(".md") else raw
        chat = os.path.realpath(os.path.join(self.chat_root, stem + CHAT_SUFFIX))
        if not chat.startswith(self.chat_root + os.sep):
            raise NoteError("非法路径")
        return raw, chat

    def load_chat(self, note_name: str) -> dict:
        real, path = self._chat_path(note_name)
        messages: list[dict] = []
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("messages"), list):
                    messages = data["messages"]
            except (OSError, ValueError):
                messages = []      # 损坏文件按空处理，面板里用户重新对话即可覆盖
        return {"note": real, "messages": messages}

    def save_chat(self, note_name: str, messages: list) -> dict:
        real, path = self._chat_path(note_name)
        cleaned: list[dict] = []
        for m in (messages or [])[-MAX_CHAT_MESSAGES:]:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            content = str(m.get("content", ""))[:MAX_CHAT_CONTENT]
            if role not in ("user", "assistant", "system") or not content:
                continue
            item = {"role": role, "content": content}
            if m.get("time"):
                item["time"] = str(m["time"])[:32]
            cleaned.append(item)
        if not cleaned:
            self.clear_chat(real)
            return {"note": real, "saved": 0}
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"note": real, "messages": cleaned}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return {"note": real, "saved": len(cleaned)}

    def clear_chat(self, note_name: str) -> dict:
        real, path = self._chat_path(note_name)
        if os.path.isfile(path):
            os.remove(path)
        return {"note": real, "cleared": True}

    def rename_chat(self, old_note: str, new_note: str) -> None:
        """笔记改名时聊天记录跟随迁移（不存在则静默）。"""
        _, old_path = self._chat_path(old_note)
        if not os.path.isfile(old_path):
            return
        _, new_path = self._chat_path(new_note)
        os.replace(old_path, new_path)

    def delete_chat_for_note(self, note_name: str) -> None:
        """供笔记删除流程调用；异常静默（笔记都删了，记录残留无害且不可达）。"""
        try:
            self.clear_chat(note_name)
        except Exception:  # noqa: BLE001
            pass
