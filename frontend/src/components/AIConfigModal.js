/** AI 服务配置弹窗（功能四）：基于通用 Modal，含 Key 明文切换与测试连接。
 *
 * 存储决策：仍走浏览器 localStorage（本机自用，避免 Key 落盘到可被同步的
 * 项目目录）；「测试连接」调 POST /api/ai/test，由本机后端代理转发验证。
 */
import { openModal } from "./Modal";
import { loadAiConfig, saveAiConfig, clearAiConfig } from "../utils/storage";
import { testConnection } from "../api/ai";
import { toast } from "./Toast";
import { setStatus } from "./StatusBar";

export function openAIConfig({ onSaved } = {}) {
  const cfg = loadAiConfig();
  const { close } = openModal({
    title: "⚙️ AI 服务配置",
    bodyHTML: `
      <div class="field">
        <label>服务地址（OpenAI 兼容 Base URL）</label>
        <input id="ai-base" type="text" placeholder="https://api.deepseek.com/v1" autocomplete="off" />
        <div class="hint">DeepSeek：https://api.deepseek.com/v1 ｜ OpenAI：https://api.openai.com/v1 ｜ Ollama：http://localhost:11434/v1</div>
      </div>
      <div class="field">
        <label>模型名称</label>
        <input id="ai-model" type="text" placeholder="deepseek-chat / gpt-4o-mini / qwen2.5" autocomplete="off" />
      </div>
      <div class="field">
        <label>API Key</label>
        <div class="pw-wrap">
          <input id="ai-key" type="password" placeholder="sk-…" autocomplete="off" />
          <button type="button" class="eye" id="ai-key-eye" aria-label="显示或隐藏 API Key"
                  aria-pressed="false" title="显示/隐藏">🙈</button>
        </div>
        <div class="hint">仅保存在本浏览器 localStorage，由本机后端代理调用，不会上传第三方。（本地 Ollama 可留空）</div>
      </div>`,
    footHTML: `
      <button class="btn btn-sm danger" data-a="clear">清除已存配置</button>
      <button class="btn btn-sm" data-a="test">测试连接</button>
      <button class="btn btn-sm" data-a="cancel">取消</button>
      <button class="btn btn-sm btn-primary" data-a="save">保存</button>`,
    onMount(root, api) {
      const $ = (id) => root.querySelector("#" + id);
      $("ai-base").value = cfg.base_url || "";
      $("ai-model").value = cfg.model || "";
      $("ai-key").value = cfg.api_key || "";

      const collect = () => ({
        base_url: $("ai-base").value.trim(),
        model: $("ai-model").value.trim(),
        api_key: $("ai-key").value.trim(),
      });

      // Key 明文切换（默认隐藏，安全要求·十一）
      const eye = $("ai-key-eye");
      const keyInput = $("ai-key");
      eye.addEventListener("click", () => {
        const show = keyInput.type === "password";
        keyInput.type = show ? "text" : "password";
        eye.textContent = show ? "👁" : "🙈";
        eye.setAttribute("aria-pressed", show ? "true" : "false");
        keyInput.focus();
      });

      root.querySelector('[data-a="cancel"]').addEventListener("click", () => api.close());

      root.querySelector('[data-a="save"]').addEventListener("click", () => {
        saveAiConfig(collect());
        api.close();
        setStatus("AI 配置已保存到本浏览器", "flash");
        if (onSaved) onSaved();
      });

      root.querySelector('[data-a="clear"]').addEventListener("click", () => {
        clearAiConfig();
        ["ai-base", "ai-model", "ai-key"].forEach((id) => { $(id).value = ""; });
        setStatus("已清除本机 AI 配置", "flash");
        if (onSaved) onSaved();
      });

      const testBtn = root.querySelector('[data-a="test"]');
      testBtn.addEventListener("click", async () => {
        const c = collect();
        if (!c.base_url || !c.model) {
          toast("请先填写服务地址与模型名称", { kind: "err" });
          return;
        }
        testBtn.disabled = true;
        testBtn.textContent = "测试中…";
        try {
          const d = await testConnection(c);
          toast(`连接成功（${d.model}）${d.echo ? "：回应 " + d.echo.slice(0, 20) : ""}`,
                { kind: "ok", ms: 4000 });
        } catch (err) {
          toast(`连接失败：${err.message}`, { kind: "err", ms: 8000 });
        } finally {
          testBtn.disabled = false;
          testBtn.textContent = "测试连接";
        }
      });
    },
  });
  return close;
}
