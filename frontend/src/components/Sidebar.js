/** 侧栏：三页签（笔记/搜索/AI）切换、笔记列表渲染、整体折叠（九.2 / 七）。 */
import { state } from "../state";
import { escapeHtml } from "../utils/misc";

const TABS = ["notes", "search", "ai"];
let openNoteCb = null;

export const Sidebar = {
  /** @param {{openNote:Function}} hooks */
  init(hooks) {
    openNoteCb = hooks.openNote;
    for (const t of TABS) {
      document.getElementById(`tab-${t}`).addEventListener("click", () => switchTab(t));
    }
    document.getElementById("btn-sidebar").addEventListener("click", () => {
      const ws = document.getElementById("workspace");
      const collapsed = ws.classList.toggle("side-collapsed");
      try { localStorage.setItem("nb.sidebar", collapsed ? "0" : "1"); } catch (_) {}
    });
    try {
      const pref = localStorage.getItem("nb.sidebar");
      const smallScreen = window.innerWidth < 860;
      if (pref === "0" || (pref === null && smallScreen)) {
        document.getElementById("workspace").classList.add("side-collapsed");
      }
    } catch (_) {}
  },

  switchTab,

  /** 渲染笔记列表（数据来自 App 统一拉取） */
  renderNotes(notes) {
    const ul = document.getElementById("note-list");
    ul.innerHTML = "";
    if (!notes.length) {
      ul.innerHTML = `<li class="note-empty">暂无笔记，点左上「＋ 新建」开始</li>`;
      return;
    }
    for (const n of notes) {
      const li = document.createElement("li");
      li.className = "note-item" + (n.name === state.fileName ? " active" : "");
      li.title = n.name;
      li.innerHTML = `<span class="ico">📄</span><span class="name"></span>` +
                     `<span class="meta">${escapeHtml(sizeOf(n.size))}</span>`;
      li.querySelector(".name").textContent = n.name;
      li.addEventListener("click", () => openNoteCb && openNoteCb(n.name));
      ul.appendChild(li);
    }
  },
};

export function switchTab(name) {
  for (const t of TABS) {
    document.getElementById(`page-${t}`).classList.toggle("hidden", t !== name);
    document.getElementById(`tab-${t}`).classList.toggle("active", t === name);
  }
}

function sizeOf(bytes) {
  if (!bytes && bytes !== 0) return "";
  return bytes > 1024 ? `${(bytes / 1024).toFixed(1)}K` : `${bytes}B`;
}
