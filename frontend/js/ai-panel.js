/* ==========================================================================
 * ai-panel.js —— AI 助手（FR-11）+ 设置弹窗（优化文档·二.1）
 *
 * · ⚙️ 弹窗配置 Base URL / 模型 / API Key，存 localStorage（仅本机）
 * · 未配置时输入框禁用 + 顶部引导横幅，点击横幅直达设置
 * · 发送时随请求携带配置，后端优先使用（env 配置兜底）
 * · 等待回复时显示三点“思考中”动画；失败给出可操作的提示
 * ========================================================================== */
window.App = window.App || {};

(function () {
  const CFG_KEY = "nb.ai.…s";
  const state = { messages: [], busy: false };
  let hintHTML = "";

  App.AIPanel = { init, isReady, openSettings };

  // ---------------- 配置存取 ----------------
  function getCfg() {
    try { return JSON.parse(localStorage.getItem(CFG_KEY)) || {}; }
    catch (_) { return {}; }
  }
  function saveCfg(cfg) { localStorage.setItem(CFG_KEY, JSON.stringify(cfg)); }

  /** 配置可用判定：base+model 必填；非本机地址还需要 key */
  function usable(cfg) {
    const base = (cfg.base_url || "").trim();
    const model = (cfg.model || "").trim();
    const key = (cfg.api_key || "").trim();
    if (!base || !model) return false;
    if (/localhost|127\.0\.0\.1/i.test(base)) return true;
    return !!key;
  }
  function isReady() { return usable(getCfg()); }

  // ---------------- 初始化 ----------------
  function init() {
    hintHTML = document.getElementById("ai-messages").innerHTML;

    document.getElementById("btn-ai-settings").addEventListener("click", openSettings);
    document.getElementById("ai-need-key").addEventListener("click", openSettings);
    document.getElementById("btn-ai-close-modal").addEventListener("click", closeModal);
    document.getElementById("btn-ai-cancel").addEventListener("click", closeModal);
    document.getElementById("ai-modal").addEventListener("click", (e) => {
      if (e.target.id === "ai-modal") closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
    document.getElementById("btn-ai-savecfg").addEventListener("click", () => {
      saveCfg({
        base_url: document.getElementById("ai-base").value.trim(),
        model: document.getElementById("ai-model").value.trim(),
        api_key: document.getElementById("ai-key").value.trim(),
      });
      closeModal();
      refreshGate();
      App.setStatus && App.setStatus("AI 配置已保存到本浏览器", "flash");
    });
    document.getElementById("btn-ai-clearcfg").addEventListener("click", () => {
      localStorage.removeItem(CFG_KEY);
      ["ai-base", "ai-model", "ai-key"].forEach((id) => (document.getElementById(id).value = ""));
      refreshGate();
    });

    document.getElementById("btn-ai-send").addEventListener("click", () =>
      send(document.getElementById("ai-input").value));
    document.getElementById("ai-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send(e.target.value);
      }
    });
    document.getElementById("btn-ai-summarize").addEventListener("click", () =>
      send("请用要点列表总结下面这份笔记的核心内容。"));
    document.getElementById("btn-ai-clear").addEventListener("click", () => {
      state.messages = [];
      document.getElementById("ai-messages").innerHTML = hintHTML;
    });

    refreshGate();
  }

  // ---------------- 配置门槛（置灰/引导） ----------------
  function refreshGate() {
    const ready = isReady();
    const input = document.getElementById("ai-input");
    const sendBtn = document.getElementById("btn-ai-send");
    const summarize = document.getElementById("btn-ai-summarize");

    input.disabled = !ready || state.busy;
    sendBtn.disabled = !ready || state.busy;
    summarize.disabled = !ready || state.busy;
    input.placeholder = ready
      ? "输入问题，Enter 发送…"
      : "请先配置 API Key 以使用 AI 助手";
    document.getElementById("ai-need-key").classList.toggle("hidden", ready);

    const st = document.getElementById("status-ai");
    if (st) {
      st.textContent = ready ? "AI：已配置" : "AI：未配置";
      st.className = ready ? "ok" : "no";
    }
  }

  function openSettings() {
    const cfg = getCfg();
    document.getElementById("ai-base").value = cfg.base_url || "";
    document.getElementById("ai-model").value = cfg.model || "";
    document.getElementById("ai-key").value = cfg.api_key || "";
    document.getElementById("ai-modal").classList.remove("hidden");
    document.getElementById("ai-base").focus();
  }
  function closeModal() {
    document.getElementById("ai-modal").classList.add("hidden");
  }

  // ---------------- 对话 ----------------
  async function send(prompt) {
    prompt = (prompt || "").trim();
    if (!prompt || state.busy) return;
    if (!isReady()) {
      App.setStatus && App.setStatus("请先配置 AI 服务（Base URL / 模型 / API Key）", "error");
      openSettings();
      return;
    }
    state.busy = true;
    refreshGate();
    document.getElementById("ai-input").value = "";

    pushBubble("user", prompt);
    state.messages.push({ role: "user", content: prompt });
    const pending = pushBubble("bot", '<span class="ai-dots"><span></span><span></span><span></span></span> 思考中…');

    const cfg = getCfg();
    try {
      const resp = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: state.messages,
          context: App.editor ? App.editor.getValue() : "",
          ai: { base_url: cfg.base_url, model: cfg.model, api_key: cfg.api_key },
        }),
      });
      const data = await resp.json();
      if (data.ok) {
        state.messages.push({ role: "assistant", content: data.reply });
        renderBot(pending, data.reply);
      } else {
        state.messages.pop();
        pending.innerHTML =
          `<span class="ai-err">⚠️ ${escapeHtml(data.error || "未知错误")}</span><br/>` +
          `<span class="ai-hint">点 ⚙️ 检查服务地址 / 模型名 / API Key</span>`;
      }
    } catch (err) {
      state.messages.pop();
      pending.innerHTML = `<span class="ai-err">请求失败：${escapeHtml(String(err))}</span>`;
    } finally {
      state.busy = false;
      refreshGate();
    }
  }

  function pushBubble(role, html) {
    const box = document.getElementById("ai-messages");
    const div = document.createElement("div");
    div.className = "ai-bubble " + (role === "user" ? "ai-user" : "ai-bot");
    if (role === "user") div.textContent = html;
    else div.innerHTML = html;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
  }

  function renderBot(el, markdownText) {
    try { el.innerHTML = marked.parse(markdownText); }
    catch (_) { el.textContent = markdownText; }
    el.querySelectorAll("pre code").forEach((c) => {
      try { hljs.highlightElement(c); } catch (_) { /* 忽略 */ }
    });
    const box = document.getElementById("ai-messages");
    box.scrollTop = box.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
})();
