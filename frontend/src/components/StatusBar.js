/** 状态栏与顶栏提示：轻量、非阻塞的反馈区（错误一律走 Toast）。 */
import { escapeHtml } from "../utils/misc";

const LANG_META = {
  python: { icon: "🐍" },
  javascript: { icon: "📦" },
  shell: { icon: "💲" },
  java: { icon: "☕" },
  go: { icon: "🐹" },
};

export function setStatus(msg, cls) {
  const el = document.getElementById("status-tip");
  if (!el) return;
  el.textContent = msg;
  el.className = cls || "";
  clearTimeout(setStatus._t);
  setStatus._t = setTimeout(() => {
    el.textContent = "就绪";
    el.className = "";
  }, 5000);
}

export function showCursor(lineNumber, column) {
  const el = document.getElementById("status-lines");
  if (el) el.textContent = `行 ${lineNumber}，列 ${column}`;
}

export function setFileName(name) {
  const el = document.getElementById("status-file");
  if (el) el.textContent = name;
}

export function setAiStatus(ready, backendConfigured) {
  const st = document.getElementById("status-ai");
  if (!st) return;
  st.textContent = ready ? "AI：已配置" : backendConfigured ? "AI：后端已配置" : "AI：未配置";
  st.className = ready || backendConfigured ? "ok" : "no";
}

/** 执行器模式徽章（侧栏底部 + 状态栏） */
export function setExecutorBadge(mode) {
  const st = document.getElementById("status-executor");
  const badge = document.getElementById("exec-badge");
  if (mode === "docker") {
    if (st) { st.textContent = "执行器：docker"; st.className = "ok"; }
    if (badge) {
      badge.className = "exec-badge docker";
      badge.textContent = "🛡️ Docker 沙箱已启用（断网 + 内存/CPU 限额）";
    }
  } else if (mode === "local") {
    if (st) st.textContent = "执行器：local";
    if (badge) {
      badge.className = "exec-badge local";
      badge.textContent = "⚠️ 代码在本地环境执行，请勿运行未知来源的笔记";
    }
  } else {
    if (st) st.textContent = "后端未连接";
  }
}

/** 状态栏语言环境灯（/api/health 的 languages 数据） */
export function setRunTimes(languages) {
  const el = document.getElementById("status-runtimes");
  const dot = document.getElementById("status-runtimes-dot");
  if (!el || !Array.isArray(languages)) return;
  el.innerHTML = languages
    .map((l) => {
      const meta = LANG_META[l.language] || { icon: "•" };
      const on = !!l.available;
      const tip = `${l.language}：${on ? l.version || "可用" : "未检测到" + (l.hint ? "（" + l.hint + "）" : "")}`;
      return `<span class="rt${on ? "" : " off"}" title="${escapeHtml(tip)}">${meta.icon}${on ? "✅" : "❌"}</span>`;
    })
    .join("");
  if (dot) dot.style.display = languages.length ? "" : "none";
}
