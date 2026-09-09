"""AI 助手服务（FR-11）：OpenAI 兼容 Chat Completions 封装。

通过环境变量配置，可接 DeepSeek / OpenAI / Ollama 等任意兼容端点：
  AI_BASE_URL  例如 https://api.deepseek.com/v1 或 http://localhost:11434/v1
  AI_API_KEY   服务端密钥（Ollama 可留空）
  AI_MODEL     模型名，如 deepseek-chat / gpt-4o-mini / qwen2.5

未配置密钥时返回明确的“未启用”提示，前端据此引导用户配置。
"""
from __future__ import annotations

try:
    import requests
except ImportError:  # pragma: no cover  未安装时 AI 功能降级为明确报错
    requests = None

SYSTEM_PROMPT = (
    "你是 Markdown 可执行笔记工具内置的编程与写作助手。"
    "回答保持简洁，代码建议以 Markdown 围栏代码块给出，"
    "如适合在笔记中运行，优先给出 Python 代码。"
)


class AIResult(dict):
    """统一返回结构：{ok, reply | error}。"""


class AIService:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model)

    def chat(
        self,
        messages: list[dict],
        context: str = "",
        overrides: dict | None = None,
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
                error="AI 服务未配置：请在 AI 助手面板右上角 ⚙️ 中填写服务地址与模型名"
                      "（也可用环境变量 AI_BASE_URL / AI_MODEL 配置默认值）。",
            )
        local = "localhost" in base_url or "127.0.0.1" in base_url
        if not api_key and not local:
            return AIResult(
                ok=False,
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
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return AIResult(ok=True, reply=reply, model=model)
        except requests.RequestException as exc:
            return AIResult(ok=False, error=f"AI 接口调用失败：{exc}")
        except (KeyError, ValueError) as exc:
            return AIResult(ok=False, error=f"AI 响应格式异常：{exc}")
