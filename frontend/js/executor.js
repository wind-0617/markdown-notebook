/* ==========================================================================
 * executor.js —— 代码块提取与执行（FR-03 / FR-06 / FR-08）
 * 新增：运行状态反馈（按钮禁用 + “运行中…” + 耗时提示），防重复点击。
 * ========================================================================== */
window.App = window.App || {};

(function () {
  const RUNNABLE = new Set(["python", "javascript", "js", "shell", "bash", "sh"]);
  const ALIAS = { js: "javascript", bash: "shell", sh: "shell" };
  const FENCE_RE = /^ {0,3}(```+|~~~+)\s*([\w+-]*)[^\n]*\n([\s\S]*?)^ {0,3}\1[ \t]*$/gm;

  /** 从 Markdown 源码提取代码块（与后端 markdown_parser 规则一致） */
  App.extractBlocks = function (source) {
    const blocks = [];
    let m;
    FENCE_RE.lastIndex = 0;
    while ((m = FENCE_RE.exec(source))) {
      const raw = (m[2] || "").toLowerCase();
      const code = m[3].replace(/\n$/, "");
      blocks.push({
        index: blocks.length,
        rawLanguage: raw,
        language: ALIAS[raw] || raw,
        code,
        startLine: source.slice(0, m.index).split("\n").length,
        runnable: RUNNABLE.has(raw),
        params: [],
      });
    }
    return blocks;
  };

  /** 找光标处（或其后、否则其前）最近的可执行块 —— Shift+Enter 语义 */
  App.blockAtLine = function (blocks, line) {
    for (const b of blocks) {
      if (b.runnable && b.startLine >= line - 1) return b;
    }
    for (const b of [...blocks].reverse()) {
      if (b.runnable && b.startLine <= line) return b;
    }
    return null;
  };

  let busyCount = 0;

  App.Executor = {
    isBusy: () => busyCount > 0,

    /** 执行指定索引的代码块，结果渲染到预览区 */
    runBlock: async function (index, source, opts) {
      opts = opts || {};
      const block = (App.Preview.blocks || []).find((b) => b.index === index);
      if (!block || !block.runnable) {
        App.setStatus && App.setStatus("光标附近没有可执行的代码块", "error");
        return;
      }
      const wrap = document.querySelector(`.nb-block[data-index="${index}"]`);
      const outputEl = wrap && wrap.querySelector(".nb-output");
      const runBtn = wrap && wrap.querySelector(".nb-run");
      if (!outputEl || wrap.dataset.busy) return;   // 防重复点击

      wrap.dataset.busy = "1";
      busyCount++;
      syncGlobalRunButton();
      setButtonRunning(runBtn, true);
      const collect = App.Preview.collectors[index];
      const values = collect ? collect() : {};
      const code = Object.keys(values).length
        ? App.buildExecutableCode(block.language, block.code, values)
        : block.code;
      outputEl.innerHTML = `<span class="nb-running">⏳ ${block.language} 执行中…</span>`;

      try {
        const resp = await fetch("/api/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            language: block.language,
            code,                     // 交互参数已在前面展开为赋值
            timeout: opts.timeout,
          }),
        });
        const result = await resp.json();
        renderResult(outputEl, result);
        App.Preview.cacheOutput(block.code, outputEl.innerHTML);   // FR-09 会话缓存
        const secs = ((result.duration_ms || 0) / 1000).toFixed(2);
        if (App.setStatus) {
          if (result.error) App.setStatus(`运行失败：${result.error}`, "error");
          else if (result.timed_out) App.setStatus(`执行超时（${secs} 秒）`, "error");
          else if (result.exit_code === 0) App.setStatus(`执行完成（${secs} 秒）`, "flash");
          else App.setStatus(`运行结束，退出码 ${result.exit_code}（${secs} 秒）`, "error");
        }
      } catch (err) {
        outputEl.innerHTML =
          `<span class="nb-err">请求后端失败：${escapeHtml(String(err))}` +
          `<br/>（请确认 Flask 服务已启动：python backend/app.py）</span>`;
        App.setStatus && App.setStatus("后端连接失败", "error");
      } finally {
        delete wrap.dataset.busy;
        busyCount = Math.max(0, busyCount - 1);
        syncGlobalRunButton();
        setButtonRunning(runBtn, false);
      }
    },

    /** 依次执行全部可运行块（调用方负责二次确认） */
    runAll: async function (source) {
      const runnable = (App.Preview.blocks || []).filter((b) => b.runnable);
      for (const b of runnable) {
        await App.Executor.runBlock(b.index, source);
      }
    },
  };

  function setButtonRunning(btn, on) {
    if (!btn) return;
    btn.disabled = on;
    btn.textContent = on ? "⏳ 运行中…" : "▶ 运行";
  }

  function syncGlobalRunButton() {
    const g = document.getElementById("btn-run");
    const ga = document.getElementById("btn-run-all");
    if (g) g.disabled = busyCount > 0;
    if (ga) ga.disabled = busyCount > 0;
  }

  function renderResult(el, r) {
    const parts = [];
    if (r.error) parts.push(`<span class="nb-err">❌ ${escapeHtml(r.error)}</span>`);
    if (r.stdout) parts.push(escapeHtml(r.stdout));
    if (r.stderr) parts.push(`<span class="nb-err">${escapeHtml(r.stderr)}</span>`);
    if (!parts.length) parts.push(`<span style="color:var(--text-faint)">（无输出）</span>`);
    parts.push(
      `<div class="nb-meta">exit=${r.exit_code ?? "-"} · ${(r.duration_ms ?? 0)} ms${
        r.timed_out ? " · 超时终止" : ""
      }</div>`
    );
    el.innerHTML = parts.join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
})();
