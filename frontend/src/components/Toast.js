/** 全局 Toast（指令文档·七：错误提示不阻塞界面）。 */

const KIND_TITLE = { err: "⚠️", ok: "✅", info: "ℹ️" };

/**
 * @param {string} message 正文（可含已消毒 HTML）
 * @param {{kind?:'info'|'err'|'ok', title?:string, ms?:number}} [opts]
 */
export function toast(message, opts = {}) {
  const { kind = "info", title, ms = 4200 } = opts;
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.setAttribute("role", "alert");
  const head = title || KIND_TITLE[kind] || "";
  el.innerHTML = `${head ? `<div class="t-title">${head}</div>` : ""}<div>${message}</div>`;
  stack.appendChild(el);
  const drop = () => {
    el.classList.add("hide");
    setTimeout(() => el.remove(), 260);
  };
  const timer = setTimeout(drop, ms);
  el.addEventListener("click", () => {
    clearTimeout(timer);
    drop();
  });
}
