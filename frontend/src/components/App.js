/** App 控制器：装配各组件、主题/布局持久化、笔记读写与运行编排（v0.3）。 */
import * as notesApi from "../api/notes";
import { health } from "../api/environment";
import { ApiError } from "../api/client";
import { setDirty, state } from "../state";
import { debounce } from "../utils/misc";
import { bindGlobalShortcuts } from "../utils/shortcuts";
import * as AIPanel from "./AIPanel";
import { Executor } from "./Executor";
import { Preview, blockAtLine, extractBlocks, applyHljsTheme } from "./Preview";
import { SearchPanel } from "./SearchPanel";
import { Sidebar } from "./Sidebar";
import { setFileName, setStatus, setExecutorBadge, setRunTimes, showCursor } from "./StatusBar";
import { toast } from "./Toast";

const LS = { theme: "nb.theme", layout: "nb.layout", autosave: "nb.autosave" };

// ==================================================================
// 启动
// ==================================================================
export async function boot() {
  applyTheme(getTheme()); // 先上主题，避免闪白
  initLayout();

  Sidebar.init({ openNote });
  SearchPanel.init({ openNote });
  AIPanel.init();

  bind("btn-new", newNote);
  bind("btn-save", () => save());
  bind("btn-run", runAtCursor);
  bind("btn-run-all", runAllConfirmed);
  bind("btn-theme", toggleTheme);
  document.querySelectorAll("#seg-layout button").forEach((b) =>
    b.addEventListener("click", () => setLayout(b.dataset.layout)));
  bindAutosave();
  bindGlobalShortcuts({ onSave: () => save(), onSearchFocus: () => SearchPanel.focus() });

  // Monaco 体积大：编辑器就绪前页面已可交互（骨架 + 提示）
  const { createEditor, cursorLine } = await import("./Editor.js");
  state.editor = createEditor(document.getElementById("editor"), {
    value: DEFAULT_NOTE,
    theme: getTheme(),
    onSave: () => save(),
    onRunAtCursor: runAtCursor,
  });

  renderPreview();
  const schedulePreview = debounce(renderPreview, 300);
  state.editor.onDidChangeModelContent(() => {
    setDirty(true);
    schedulePreview();
    updateFileTabDebounced();
  });
  state.editor.onDidChangeCursorPosition((e) =>
    showCursor(e.position.lineNumber, e.position.column));

  await refreshNotes();
  await refreshEnvironment();
  updateFileTab();
  setDirty(false);

  setInterval(() => {
    const autosaveOn = localStorage.getItem(LS.autosave) === "1";
    if (autosaveOn && state.dirty) save({ silent: true });
  }, 10_000);

  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) { e.preventDefault(); e.returnValue = ""; }
  });
}

function bind(id, fn) {
  const el = document.getElementById(id);
  if (el && fn) el.addEventListener("click", fn);
}

// ==================================================================
// 预览与执行
// ==================================================================
function renderPreview() {
  Preview.render(state.editor.getValue(), (index) => Executor.runBlock(index));
}

function runAtCursor() {
  if (!state.editor) return; // Monaco 尚未就绪
  const p = state.editor.getPosition();
  const line = p ? p.lineNumber : 1;
  const blocks = extractBlocks(state.editor.getValue());
  const block = blockAtLine(blocks, line);
  if (!block) {
    toast("光标处及附近没有可执行代码块（支持 ```python / ```javascript / ```shell / ```java / ```go）", { kind: "err" });
    return;
  }
  renderPreview(); // 先确保 DOM 与源码一致
  setTimeout(() => Executor.runBlock(block.index), 0);
}

function runAllConfirmed() {
  const blocks = extractBlocks(state.editor.getValue());
  const runnable = blocks.filter((b) => b.runnable);
  if (!runnable.length) {
    toast("没有可执行的代码块", { kind: "err" });
    return;
  }
  const ok = window.confirm(
    `将依次执行 ${runnable.length} 个代码块。\n\n` +
    `注意：每个代码块在独立进程中运行，块与块之间不共享变量（无持久内核）。\n` +
    `如有依赖关系的代码请逐个手动运行。\n\n确认继续？`);
  if (!ok) return;
  renderPreview();
  Executor.runAll();
}

// ==================================================================
// 笔记文件管理（FR-05）
// ==================================================================
async function refreshNotes() {
  try {
    Sidebar.renderNotes(await notesApi.listNotes());
  } catch (err) {
    setStatus("无法读取笔记列表：" + err.message, "error");
  }
}

async function openNote(name) {
  if (state.dirty &&
      !confirm(`「${state.fileName}」有未保存修改，放弃并打开 ${name}？`)) return;
  try {
    const data = await notesApi.readNote(name);
    state.fileName = data.name || name;
    state.editor.setValue(data.content);
    setDirty(false);
    updateFileTab();
    refreshNotes();
  } catch (err) {
    toast(`打开笔记失败：${err.message}`, { kind: "err" });
  }
}

async function save(opts = {}) {
  const name = (state.fileName || "").trim() || "未命名.md";
  try {
    const data = await notesApi.saveNote(name, state.editor.getValue());
    state.fileName = data.name || name;
    setDirty(false);
    if (!opts.silent) setStatus(`已保存 ${state.fileName}`, "flash");
    refreshNotes();
  } catch (err) {
    if (opts.silent) setStatus("自动保存失败：" + err.message, "error");
    else toast(`保存失败：${err.message}`, { kind: "err" });
  }
}

async function newNote() {
  const name = prompt("新笔记文件名（无需后缀）：", "新笔记");
  if (!name) return;
  const file = name.endsWith(".md") ? name : name + ".md";
  try {
    await notesApi.createNote(file);
    state.fileName = file;
    state.editor.setValue(`# ${file.replace(/\.md$/, "")}\n\n`);
    setDirty(true);
    updateFileTab();
    refreshNotes();
  } catch (err) {
    toast(`新建失败：${err.message}`, { kind: "err" });
  }
}

// ==================================================================
// 标签栏：文件名 + H1 友好名（优化文档·二.4）
// ==================================================================
function friendlyName(content) {
  const m = /^#\s+(.+?)\s*$/m.exec(content || "");
  return m ? m[1].trim() : String(state.fileName).replace(/\.md$/i, "");
}
function updateFileTab() {
  const name = friendlyName(state.editor ? state.editor.getValue() : "");
  const el = document.getElementById("file-tab-name");
  el.textContent = name;
  document.getElementById("file-tab").title = `${name}（${state.fileName}）`;
  setFileName(state.fileName);
}
const updateFileTabDebounced = debounce(() => {
  if (state.editor) updateFileTab();
}, 400);

// ==================================================================
// 主题 / 布局 / 自动保存
// ==================================================================
function getTheme() { return localStorage.getItem(LS.theme) || "dark"; }

function applyTheme(t) {
  state.theme = t;
  document.documentElement.dataset.theme = t;
  document.getElementById("btn-theme").textContent = t === "dark" ? "☀️" : "🌙";
  applyHljsTheme(t);
  import("./Editor.js").then((m) => m.applyMonacoTheme(t)).catch(() => {});
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(LS.theme, next);
  applyTheme(next);
  setStatus(next === "dark" ? "已切换到深色主题" : "已切换到浅色主题");
}

function setLayout(mode, quiet) {
  document.getElementById("workspace").dataset.layout = mode;
  localStorage.setItem(LS.layout, mode);
  document.querySelectorAll("#seg-layout button").forEach((b) =>
    b.classList.toggle("active", b.dataset.layout === mode));
  if (!quiet) {
    setStatus({ editor: "仅编辑模式", split: "分栏模式（推荐）", preview: "仅预览模式" }[mode]);
  }
}
function initLayout() {
  setLayout(localStorage.getItem(LS.layout) || "split", true);
}

function bindAutosave() {
  const btn = document.getElementById("btn-autosave");
  const sync = () => btn.setAttribute("aria-pressed",
    localStorage.getItem(LS.autosave) === "1" ? "true" : "false");
  sync();
  btn.addEventListener("click", () => {
    const on = btn.getAttribute("aria-pressed") !== "true";
    localStorage.setItem(LS.autosave, on ? "1" : "0");
    sync();
    setStatus(on ? "自动保存已开启（每 10 秒）" : "自动保存已关闭");
  });
}

// ==================================================================
// 环境与健康（九.4）
// ==================================================================
async function refreshEnvironment() {
  try {
    const h = await health();
    setExecutorBadge(h.executor_mode);
    setRunTimes(h.languages);
    state.aiConfigured = !!h.ai_configured;
    AIPanel.refreshGate();
  } catch (err) {
    setExecutorBadge(null);
    if (err instanceof ApiError && err.code === "NETWORK") {
      toast("无法连接本地 API —— 请确认后端已启动（python backend/app.py）", { kind: "err", ms: 8000 });
    }
  }
}

// ==================================================================
export const DEFAULT_NOTE = [
  "# 欢迎使用 Markdown 可执行笔记",
  "",
  "把光标放进下面的代码块，按 **Shift+Enter** 运行它（语言由围栏 ```python 声明）：",
  "",
  "```python",
  "import math",
  "",
  "# @param r 半径 slider min=1 max=50 step=1 default=10",
  "area = math.pi * r ** 2",
  "print(f'半径 {r} 的圆面积为 {area:.2f}')",
  "```",
  "",
  "> 💡 拖动预览区的滑块会自动重新执行；🔍 页签（或 Ctrl+K）全文搜索；",
  "> 支持 python / javascript / shell / java / go 五种语言，",
  "> 每个代码块独立运行，块与块之间不共享变量。",
  "",
].join("\n");
