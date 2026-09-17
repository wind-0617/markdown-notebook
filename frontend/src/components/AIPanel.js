/** AI 助手（FR-11）+ 设置弹窗。
 *
 * · ⚙️ 配置 Base URL / 模型 / API Key → localStorage（仅本机），随请求 overrides 透传
 * · 未配置时输入框禁用 + 引导横幅；后端 env 已配置则横幅隐藏（状态栏提示“后端已配置”）
 * · v0.3：走统一信封 API；错误码 AI_NOT_CONFIGURED 直达设置弹窗
 */
import { marked } from "marked";
import hljs from "highlight.js/lib/common";

import { chat } from "../api/ai";
import { ApiError } from "../api/client";
import { state } from "../state";
import { escapeHtml } from "../utils/misc";
import { setAiStatus, setStatus } from "./StatusBar";
import { toast } from "./Toast";

const CFG_KEY = "nb.ai.…s";
const local = { messages: [], busy: false };
let hintHTML = "";

// ---------------- 配置存取 ----------------
function getCfg() {
  try { return JSON.parse(localStorage.getItem(CFG_KEY)) || {}; }
  catch (_) { return {}; }
}
function saveCfg(cfg) { localStorage.setItem(CFG_KEY, JSON.stringify(cfg)); }

/** base+model 必填；非本机地址还需要 key */
function usable(cfg) {
  const base = (cfg.base_url || "").trim();
  const model = (cfg.model || "").trim();
  const key = (cfg.api_key || "").trim();
  if (!base || !model) return false;
  if (/localhost|127\.0\.0\.1/i.test(base)) return true;
  return !!key;
}
export function isReady() { return usable(getCfg()); }

// ---------------- 初始化 ----------------
export function init() {
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
    setStatus("AI 配置已保存到本浏览器", "flash");
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
    local.messages = [];
    document.getElementById("ai-messages").innerHTML = hintHTML;
  });

  refreshGate();
}

// ---------------- 配置门槛（置灰/引导） ----------------
export function refreshGate() {
  const ready = isReady();
  const backendReady = !!state.aiConfigured && !ready;
  const input = document.getElementById("ai-input");
  const sendBtn = document.getElementById("btn-ai-send");
  const summarize = document.getElementById("btn-ai-summarize");
  const gateOpen = ready || !!state.aiConfigured;

  input.disabled = !gateOpen || local.busy;
  sendBtn.disabled = !gateOpen || local.busy;
  summarize.disabled = !gateOpen || local.busy;
  input.placeholder = gateOpen
    ? "输入问题，Enter 发送…"
    : "请先配置 API Key 以使用 AI 助手";
  document.getElementById("ai-need-key").classList.toggle("hidden", gateOpen);

  setAiStatus(ready, backendReady);
}

export function openSettings() {
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
export async function send(prompt) {
  prompt = (prompt || "").trim();
  if (!prompt || local.busy) return;
  if (!isReady() && !state.aiConfigured) {
    toast("请先配置 AI 服务（Base URL / 模型 / API Key）", { kind: "err" });
    openSettings();
    return;
  }
  local.busy = true;
  refreshGate();
  document.getElementById("ai-input").value = "";

  pushBubble("user", prompt);
  local.messages.push({ role: "user", content: prompt });
  const pending = pushBubble("bot", '<span class="ai-dots"><span></span><span></span><span></span></span> 思考中…');

  const cfg = getCfg();
  try {
    const data = await chat({
      messages: local.messages,
      context: state.editor ? state.editor.getValue() : "",
      ai: usable(cfg) ? { base_url: cfg.base_url, model: cfg.model, api_key: cfg.api_key } : null,
    });
    local.messages.push({ role: "assistant", content: data.reply });
    renderBot(pending, data.reply);
  } catch (err) {
    local.messages.pop();
    if (err instanceof ApiError && err.code === "AI_NOT_CONFIGURED") {
      pending.innerHTML =
        `<span class="ai-err">⚠️ ${escapeHtml(err.message)}</span><br/>` +
        `<span class="ai-hint">点 ⚙️ 配置服务地址 / 模型名 / API Key</span>`;
      openSettings();
    } else {
      pending.innerHTML =
        `<span class="ai-err">⚠️ ${escapeHtml(err.message || String(err))}</span><br/>` +
        `<span class="ai-hint">点 ⚙️ 检查服务地址 / 模型名 / API Key</span>`;
    }
  } finally {
    local.busy = false;
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
