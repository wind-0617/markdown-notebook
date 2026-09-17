/** 全文搜索面板（九.3）：300ms 防抖查询 Whoosh 索引，点击结果直达笔记。 */
import { rebuildIndex, search } from "../api/search";
import { debounce } from "../utils/misc";
import { setStatus } from "./StatusBar";
import { toast } from "./Toast";
import { switchTab } from "./Sidebar";
import { fmtTime } from "../utils/misc";

let openNoteCb = null;
let seq = 0; // 过期响应丢弃（慢查询不得覆盖新查询）

const runSearch = debounce((q) => doSearch(q), 300);

export const SearchPanel = {
  /** @param {{openNote:Function}} hooks */
  init(hooks) {
    openNoteCb = hooks.openNote;
    const input = document.getElementById("search-input");
    input.addEventListener("input", () => {
      const q = input.value.trim();
      if (!q) { clearResults(""); return; }
      showState("搜索中…");
      runSearch(q);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runSearch.cancel();
        const q = input.value.trim();
        if (q) doSearch(q);
      }
    });
    document.getElementById("btn-reindex").addEventListener("click", async () => {
      try {
        const d = await rebuildIndex();
        toast(`索引已重建，共收录 ${d.indexed} 篇笔记`, { kind: "ok" });
        const q = input.value.trim();
        if (q) doSearch(q);
      } catch (err) {
        toast(`索引重建失败：${err.message}`, { kind: "err" });
      }
    });
  },

  /** Ctrl+K：切到搜索页签并聚焦 */
  focus() {
    switchTab("search");
    const input = document.getElementById("search-input");
    input.focus();
    input.select();
  },
};

async function doSearch(q) {
  const my = ++seq;
  try {
    const data = await search(q);
    if (my !== seq) return;
    renderResults(data);
  } catch (err) {
    if (my !== seq) return;
    clearResults(`搜索失败：${err.message}`);
    setStatus("搜索失败", "error");
  }
}

function renderResults(data) {
  const ul = document.getElementById("search-results");
  ul.innerHTML = "";
  const results = data.results || [];
  if (!results.length) {
    clearResults(`没有匹配「${data.query}」的笔记`);
    return;
  }
  showState(`${results.length} 篇匹配 ·「${data.query}」`);
  for (const r of results) {
    const li = document.createElement("li");
    li.className = "search-item";
    li.title = r.name;
    // snippet 由后端生成：已 HTML 转义、仅含 <u> 标签，可直接注入
    li.innerHTML =
      `<div class="s-title"><span>${escapeTitle(r.title)}</span>` +
      `<time>${fmtTime(r.modified)}</time></div>` +
      `<div class="s-snip">${r.snippet || ""}</div>`;
    li.addEventListener("click", () => openNoteCb && openNoteCb(r.name));
    ul.appendChild(li);
  }
}

function escapeTitle(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showState(text) {
  const el = document.getElementById("search-state");
  el.textContent = text;
  el.classList.remove("hidden");
}

function clearResults(stateText) {
  document.getElementById("search-results").innerHTML = "";
  const el = document.getElementById("search-state");
  if (stateText) {
    el.textContent = stateText;
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}
