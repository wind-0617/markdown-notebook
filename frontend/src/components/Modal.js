/** 通用 Modal 基础组件（规范·六：所有弹窗复用统一基础件）。
 *
 * 动态生成遮罩层，复用 main.css 既有 .modal-backdrop/.modal-card/.modal-foot 样式。
 * 关闭途径：右上角 ✕ / 点遮罩 / Esc —— 一律以 cancelValue（默认 null）兑现 Promise。
 */
import { escapeHtml } from "../utils/misc";

let layer = 0;

/**
 * @param {{title:string, bodyHTML?:string, footHTML?:string,
 *          onMount?:(root:HTMLElement, api:object)=>void, cancelValue?:any}} opts
 * @returns {{el:HTMLElement, close:(result?:any)=>void, done:Promise<any>}}
 */
export function openModal(opts) {
  const { title, bodyHTML = "", footHTML = "", onMount, cancelValue = null } = opts;
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.style.zIndex = String(1200 + layer);
  backdrop.innerHTML =
    `<div class="modal-card" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">` +
      `<header><span>${escapeHtml(title)}</span>` +
        `<button class="x" data-a="dismiss" aria-label="关闭" title="关闭">✕</button></header>` +
      `<div class="modal-body">${bodyHTML}</div>` +
      (footHTML ? `<div class="modal-foot">${footHTML}</div>` : "") +
    `</div>`;

  let settled = false;
  let settle = () => {};
  const done = new Promise((r) => { settle = r; });

  const onKey = (e) => { if (e.key === "Escape") api.close(cancelValue); };
  const api = {
    el: backdrop,
    done,
    close(result) {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      backdrop.remove();
      settle(result === undefined ? cancelValue : result);
    },
  };

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop || e.target.dataset.a === "dismiss") api.close(cancelValue);
  });
  document.addEventListener("keydown", onKey, true);
  layer += 1;
  document.body.appendChild(backdrop);

  // 初始焦点：第一个文本输入，否则主按钮（键盘可无障碍直达）
  const first = backdrop.querySelector("input, textarea") || backdrop.querySelector(".btn-primary");
  if (first) setTimeout(() => first.focus(), 0);

  if (onMount) onMount(backdrop, api);
  return api;
}

/** 危险操作二次确认（删除笔记 / 清空聊天记录等）。true=确认 */
export function confirmModal({
  title = "确认操作", message, detail = "",
  confirmText = "确认", cancelText = "取消", danger = false,
}) {
  const { done } = openModal({
    title,
    bodyHTML:
      `<div class="confirm-msg">${escapeHtml(message)}</div>` +
      (detail ? `<div class="confirm-detail">${escapeHtml(detail)}</div>` : ""),
    footHTML:
      `<button class="btn btn-sm" data-a="cancel">${escapeHtml(cancelText)}</button>` +
      `<button class="btn btn-sm ${danger ? "btn-danger-solid" : "btn-primary"}" data-a="ok">` +
        `${escapeHtml(confirmText)}</button>`,
    onMount(root, api) {
      root.querySelector('[data-a="cancel"]').addEventListener("click", () => api.close(false));
      root.querySelector('[data-a="ok"]').addEventListener("click", () => api.close(true));
    },
    cancelValue: false,
  });
  return done;
}

/** 单输入框弹窗（重命名等）。resolve 修剪后的字符串；取消/关闭 resolve(null)；空串不允许通过。 */
export function promptModal({
  title = "输入", label = "", value = "", placeholder = "",
  confirmText = "确定", help = "",
}) {
  const { done } = openModal({
    title,
    bodyHTML:
      `<div class="field">` +
        (label ? `<label>${escapeHtml(label)}</label>` : "") +
        `<input type="text" placeholder="${escapeHtml(placeholder)}" autocomplete="off" />` +
        (help ? `<div class="hint">${escapeHtml(help)}</div>` : "") +
      `</div>`,
    footHTML:
      `<button class="btn btn-sm" data-a="cancel">取消</button>` +
      `<button class="btn btn-sm btn-primary" data-a="ok">${escapeHtml(confirmText)}</button>`,
    onMount(root, api) {
      const input = root.querySelector("input");
      input.value = value;
      input.select();
      const ok = () => {
        const v = input.value.trim();
        if (!v) { input.focus(); return; }        // 空值不关闭，焦点回输入框
        api.close(v);
      };
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); ok(); }   // Enter=确认
      });
      root.querySelector('[data-a="cancel"]').addEventListener("click", () => api.close(null));
      root.querySelector('[data-a="ok"]').addEventListener("click", ok);
    },
    cancelValue: null,
  });
  return done;
}
