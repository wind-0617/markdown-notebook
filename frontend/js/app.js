/* ==========================================================================
 * app.js —— 主应用逻辑（v2）
 * 主题/布局/自动保存持久化 · 侧栏双页签 · 标签栏友好名 · 运行全部二次确认
 * ========================================================================== */
window.App = window.App || {};

(function () {
  const LS = {
    theme: "nb.theme",
    layout: "nb.layout",
    autosave: "nb.autosave",
  };
  const state = {
    fileName: "未命名.md",
    dirty: false,
    editor: null,
  };
  App.editor = null;   // 供 ai-panel 读取

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();          // 先上主题，避免闪白
    initLayout();
    init();
  });

  // ==================================================================
  async function init() {
    state.editor = await App.createEditor(
      document.getElementById("editor"), DEFAULT_NOTE, getTheme());
    App.editor = state.editor;

    // ---- 预览 ----
    renderPreview();
    const schedulePreview = App.debounce(renderPreview, 300);
    state.editor.onDidChangeModelContent(() => {
      markDirty(true);
      schedulePreview();
      updateFileTabDebounced();
    });
    state.editor.onDidChangeCursorPosition((e) => {
      document.getElementById("status-lines").textContent =
        `行 ${e.position.lineNumber}，列 ${e.position.column}`;
    });

    // ---- 快捷键（FR-06）----
    state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => save());
    state.editor.addCommand(
      monaco.KeyMod.Shift | monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, runAtCursor);
    state.editor.addCommand(monaco.KeyMod.Shift | monaco.KeyCode.Enter, runAtCursor);

    // ---- 顶部工具栏 ----
    bind("btn-new", newNote);
    bind("btn-save", () => save());
    bind("btn-run", runAtCursor);
    bind("btn-run-all", runAllConfirmed);
    bind("btn-theme", toggleTheme);
    bindTopbarSegments();
    bindAutosave();

    // ---- 侧栏双页签（笔记 / AI）----
    bind("tab-notes", () => switchSidebarTab("notes"));
    bind("tab-ai", () => switchSidebarTab("ai"));

    // ---- AI 面板 ----
    App.AIPanel.init();

    await loadNoteList();
    await refreshEnvironment();
    updateFileTab();
    markDirty(false);

    setInterval(() => {
      const autosaveOn = localStorage.getItem(LS.autosave) === "1";
      if (autosaveOn && state.dirty) save({ silent: true });
    }, 10_000);

    window.addEventListener("beforeunload", (e) => {
      if (state.dirty) { e.preventDefault(); e.returnValue = ""; }
    });
  }

  function bind(id, fn) {
    document.getElementById(id).addEventListener("click", fn);
  }

  // ==================================================================
  // 预览与执行
  // ==================================================================
  function renderPreview() {
    App.Preview.render(state.editor.getValue(), (index) =>
      App.Executor.runBlock(index, state.editor.getValue()));
  }

  function runAtCursor() {
    const line = App.cursorLine(state.editor);
    const blocks = App.extractBlocks(state.editor.getValue());
    const block = App.blockAtLine(blocks, line);
    if (!block) {
      setStatus("光标处及附近没有可执行代码块（```python / ```javascript / ```shell）", "error");
      return;
    }
    renderPreview();                       // 先确保 DOM 与源码一致
    setTimeout(() => App.Executor.runBlock(block.index, state.editor.getValue()), 0);
  }

  /** 运行全部：独立执行、无共享内核 —— 先二次确认（优化文档·四.2） */
  function runAllConfirmed() {
    const blocks = App.extractBlocks(state.editor.getValue());
    const runnable = blocks.filter((b) => b.runnable);
    if (!runnable.length) {
      setStatus("没有可执行的代码块", "error");
      return;
    }
    const ok = window.confirm(
      `将依次执行 ${runnable.length} 个代码块。\n\n` +
      `注意：每个代码块在独立进程中运行，块与块之间不共享变量（无持久内核）。\n` +
      `如有依赖关系的代码请逐个手动运行。\n\n确认继续？`);
    if (!ok) return;
    renderPreview();
    App.Executor.runAll(state.editor.getValue());
  }

  // ==================================================================
  // 文件管理（FR-05）
  // ==================================================================
  async function loadNoteList() {
    try {
      const { notes } = await (await fetch("/api/notes")).json();
      const ul = document.getElementById("note-list");
      ul.innerHTML = "";
      const list = notes || [];
      if (!list.length) {
        ul.innerHTML = `<li class="note-empty">暂无笔记，点左上「＋ 新建」开始</li>`;
        return;
      }
      list.forEach((n) => {
        const li = document.createElement("li");
        li.className = "note-item" + (n.name === state.fileName ? " active" : "");
        li.title = n.name;
        li.innerHTML = `<span class="ico">📄</span><span class="name"></span>`;
        li.querySelector(".name").textContent = n.name;   // 只显示文件名（优化文档·二.4）
        li.addEventListener("click", () => openNote(n.name));
        ul.appendChild(li);
      });
    } catch (err) {
      setStatus("无法读取笔记列表：" + err.message, "error");
    }
  }

  async function openNote(name) {
    if (state.dirty && !confirm(`「${state.fileName}」有未保存修改，放弃并打开 ${name}？`)) return;
    const resp = await fetch(`/api/notes/${encodeURIComponent(name)}`);
    const data = await resp.json();
    if (data.error) return setStatus(data.error, "error");
    state.fileName = name;
    state.editor.setValue(data.content);
    markDirty(false);
    updateFileTab();
    loadNoteList();
  }

  async function save(opts) {
    opts = opts || {};
    const name = state.fileName.trim() || "未命名.md";
    const resp = await fetch(`/api/notes/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: state.editor.getValue() }),
    });
    const data = await resp.json();
    if (data.error) return setStatus("保存失败：" + data.error, "error");
    markDirty(false);
    if (!opts.silent) setStatus(`已保存 ${name}`, "flash");
    loadNoteList();
  }

  function newNote() {
    const name = prompt("新笔记文件名（无需后缀）：", "新笔记");
    if (!name) return;
    const file = name.endsWith(".md") ? name : name + ".md";
    fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: file }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.error) return setStatus(data.error, "error");
        state.fileName = file;
        state.editor.setValue(`# ${file.replace(/\.md$/, "")}\n\n`);
        markDirty(true);
        updateFileTab();
        loadNoteList();
      });
  }

  // ==================================================================
  // 标签栏：文件名 + H1 友好名 + 脏点（优化文档·二.4）
  // ==================================================================
  function friendlyName(content) {
    const m = /^#\s+(.+?)\s*$/m.exec(content || "");
    return m ? m[1].trim() : state.fileName.replace(/\.md$/i, "");
  }
  function updateFileTab() {
    const name = friendlyName(state.editor.getValue());
    const el = document.getElementById("file-tab-name");
    el.textContent = name;
    document.getElementById("file-tab").title = `${name}（${state.fileName}）`;
    document.getElementById("status-file").textContent = state.fileName;
    document.getElementById("file-tab-dirty").classList.toggle("hidden", !state.dirty);
  }
  const updateFileTabDebounced = App.debounce(() => {
    if (state.editor) updateFileTab();
  }, 400);

  function markDirty(v) {
    state.dirty = v;
    document.getElementById("status-dirty").textContent = v ? "● 未保存" : "";
    document.getElementById("file-tab-dirty").classList.toggle("hidden", !v);
  }

  // ==================================================================
  // 主题（优化文档·三.4）
  // ==================================================================
  function getTheme() { return localStorage.getItem(LS.theme) || "dark"; }
  function applyTheme(t) {
    document.documentElement.dataset.theme = t;
    document.getElementById("btn-theme").textContent = t === "dark" ? "☀️" : "🌙";
    const link = document.getElementById("hljs-theme");
    link.href = window.assetBase()
      + "/gh/highlightjs/cdn-release@11.9.0/build/styles/"
      + (t === "dark" ? "github-dark" : "github") + ".min.css";
    if (App.editor) App.applyMonacoTheme(t);
  }
  function initTheme() { applyTheme(getTheme()); }
  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem(LS.theme, next);
    applyTheme(next);
    setStatus(next === "dark" ? "已切换到深色主题" : "已切换到浅色主题");
  }

  // ==================================================================
  // 布局三段切换（优化文档·二.3）
  // ==================================================================
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
  function bindTopbarSegments() {
    document.querySelectorAll("#seg-layout button").forEach((b) =>
      b.addEventListener("click", () => setLayout(b.dataset.layout)));
  }

  // ==================================================================
  // 自动保存开关（优化文档·四.3）
  // ==================================================================
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
  // 侧栏页签
  // ==================================================================
  function switchSidebarTab(name) {
    ["notes", "ai"].forEach((t) => {
      document.getElementById("page-" + t).classList.toggle("hidden", t !== name);
      document.getElementById("tab-" + t).classList.toggle("active", t === name);
    });
  }
  App.switchSidebarTab = switchSidebarTab;

  // ==================================================================
  // 状态与环境
  // ==================================================================
  App.setStatus = function (msg, cls) { setStatus(msg, cls); };

  function setStatus(msg, cls) {
    const el = document.getElementById("status-tip");
    el.textContent = msg;
    el.className = cls || "";
    clearTimeout(setStatus._t);
    setStatus._t = setTimeout(() => {
      el.textContent = "就绪";
      el.className = "";
    }, 5000);
  }

  /** 执行器模式 + 安全提示（优化文档·五.2） */
  async function refreshEnvironment() {
    try {
      const h = await (await fetch("/api/health")).json();
      const badge = document.getElementById("exec-badge");
      const st = document.getElementById("status-executor");
      if ((h.executor_mode || "local") === "docker") {
        st.textContent = "执行器：docker";
        st.className = "ok";
        badge.className = "exec-badge docker";
        badge.textContent = "🛡️ Docker 沙箱已启用（断网 + 内存/CPU 限额）";
      } else {
        st.textContent = "执行器：local";
        badge.className = "exec-badge local";
        badge.textContent = "⚠️ 代码在本地环境执行，请勿运行未知来源的笔记";
      }
    } catch (_) {
      document.getElementById("status-executor").textContent = "后端未连接";
    }
  }

  const DEFAULT_NOTE = [
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
    "> 💡 拖动预览区的滑块会自动重新执行；右上角 ⚙️ 可配置 AI 助手；",
    "> 每个代码块独立运行，块与块之间不共享变量。",
    "",
  ].join("\n");
})();
