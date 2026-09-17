/** AI 助手（FR-11）：对话 + 配置弹窗（功能四）+ 与笔记绑定的聊天记录（功能五）。
 *
 * · 配置：localStorage（utils/storage），⚙️ 弹窗含明文切换与测试连接
 * · 未配置时输入框禁用 + 引导横幅；后端 env 已配置则横幅隐藏
 * · 聊天记录：每次成功问答后 POST /api/ai/chat/<笔记名>；打开笔记时加载恢复；
 *   🧹 清空前二次确认；随笔记删除/改名由后端自动处理
 * · v0.3：统一信封 API；错误码 AI_NOT_CONFIGURED 直达设置弹窗
 */
import { marked } from "marked";
import hljs from "highlight.js/lib/common";

import { chat, loadChat, saveChat, clearChat } from "../api/ai";
import { ApiError } from "../api/client";
import { state } from "../state";
import { escapeHtml } from "../utils/misc";
import { loadAiConfig, aiConfigUsable } from "../utils/storage";
import { confirmModal } from "./Modal";
import { openAIConfig } from "./AIConfigModal";
import { setAiStatus, setStatus } from "./StatusBar";
import { toast } from "./Toast";

const local = { messages: [], busy: false };
let hintHTML = "";
let chatNote = "未命名.md";      // 当前聊天记录归属的笔记名

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

// ---------------- 初始化 ----------------
export function init() {
  hintHTML = document.getElementById("ai-messages").innerHTML;

  document.getElementById("btn-ai-settings").addEventListener("click", openSettings);
  document.getElementById("ai-need-key").addEventListener("click", openSettings);

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
  document.getElementById("btn-ai-clear").addEventListener("click", clearConversation);

  refreshGate();
}

// ---------------- 配置门槛（置灰/引导，功能四验收点） ----------------
export function isReady() { return aiConfigUsable(loadAiConfig()); }

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
  openAIConfig({ onSaved: refreshGate });
}

// ---------------- 聊天记录：加载 / 渲染（功能五） ----------------
export async function onNoteOpened(name) {
  const note = name || "未命名.md";
  chatNote = note;
  let msgs = [];
  try {
    msgs = await loadChat(note);
  } catch (_) {
    msgs = [];                     // 后端未启动 / 记录不存在：按空会话处理
  }
  if (chatNote !== note) return;   // 加载期间用户又切了笔记：丢弃过期响应
  local.messages = msgs;
  renderAll();
}

/** 笔记换名（首次保存/另存）时迁移聊天记录：旧名读 → 新名写 → 清旧档。 */
export async function migrateChat(from, to) {
  if (!from || !to || from === to) return;
  try {
    const msgs = await loadChat(from);
    if (!msgs.length) return;
    await saveChat(to, msgs);
    await clearChat(from);
    if (chatNote === from) chatNote = to;
  } catch (_) { /* 迁移尽力而为，失败不打断编辑流程 */ }
}

function renderAll() {
  const box = document.getElementById("ai-messages");
  box.innerHTML = "";
  if (!local.messages.length) {
    box.innerHTML = hintHTML;
    return;
  }
  for (const m of local.messages) {
    if (m.role === "user") pushBubble("user", m.content, m.time);
    else renderBot(pushBubble("bot", "", m.time), m.content);
  }
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

  const userMsg = { role: "user", content: prompt, time: stamp() };
  pushBubble("user", prompt, userMsg.time);
  local.messages.push(userMsg);
  const pending = pushBubble("bot", '<span class="ai-dots"><span></span><span></span><span></span></span> 思考中…');

  const cfg = loadAiConfig();
  const owner = chatNote;
  try {
    const data = await chat({
      messages: local.messages,
      context: state.editor ? state.editor.getValue() : "",
      ai: aiConfigUsable(cfg) ? { base_url: cfg.base_url, model: cfg.model, api_key: cfg.api_key } : null,
    });
    const botMsg = { role: "assistant", content: data.reply, time: stamp() };
    local.messages.push(botMsg);
    renderBot(pending, data.reply);
    appendTime(pending, botMsg.time);       // 会话内即时补时间戳（与恢复视图一致）
    // 追加落盘（后端按 owner 写 <笔记>.ai-chat.json；失败仅提示不打断会话）
    saveChat(owner, local.messages).catch((err) =>
      toast(`聊天记录保存失败：${err.message}`, { kind: "err" }));
  } catch (err) {
    local.messages.pop();
    pending.closest(".ai-bubble").remove(); // 清掉“思考中”占位气泡整体
    if (err instanceof ApiError && err.code === "AI_NOT_CONFIGURED") {
      const e = pushBubble("bot", "");
      e.innerHTML =
        `<span class="ai-err">⚠️ ${escapeHtml(err.message)}</span><br/>` +
        `<span class="ai-hint">点 ⚙️ 配置服务地址 / 模型名 / API Key</span>`;
      openSettings();
    } else {
      const e = pushBubble("bot", "");
      e.innerHTML =
        `<span class="ai-err">⚠️ ${escapeHtml(err.message || String(err))}</span><br/>` +
        `<span class="ai-hint">点 ⚙️ 检查服务地址 / 模型名 / API Key</span>`;
    }
  } finally {
    local.busy = false;
    refreshGate();
  }
}

// ---------------- 清空（二次确认，危险操作规范） ----------------
async function clearConversation() {
  const yes = await confirmModal({
    title: "清空聊天记录",
    message: `确定清空「${chatNote}」的全部聊天记录吗？`,
    detail: "此操作不可恢复。",
    confirmText: "清空",
    danger: true,
  });
  if (!yes) return;
  try {
    await clearChat(chatNote);
  } catch (err) {
    toast(`清空失败：${err.message}`, { kind: "err" });
    return;
  }
  local.messages = [];
  renderAll();
  setStatus("聊天记录已清空", "flash");
}

// ---------------- 气泡渲染 ----------------
function appendTime(bodyEl, time) {
  const bubble = bodyEl.closest(".ai-bubble");
  if (!bubble || bubble.querySelector(".msg-time")) return;
  const t = document.createElement("span");
  t.className = "msg-time";
  t.textContent = time;
  bubble.appendChild(t);
}

function pushBubble(role, html, time) {
  const box = document.getElementById("ai-messages");
  const div = document.createElement("div");
  div.className = "ai-bubble " + (role === "user" ? "ai-user" : "ai-bot");
  const body = document.createElement("div");
  body.className = "ai-body";
  if (role === "user") body.textContent = html;
  else body.innerHTML = html;
  div.appendChild(body);
  if (time) {
    const t = document.createElement("span");
    t.className = "msg-time";
    t.textContent = time;
    div.appendChild(t);
  }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return body;
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
