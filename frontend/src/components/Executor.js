/** 代码块执行（FR-03/06/08）：/api/execute 封装 + 运行状态反馈 + 防重复点击。 */
import { execute as apiExecute } from "../api/execute";
import { ApiError } from "../api/client";
import { state } from "../state";
import { codeHash, escapeHtml } from "../utils/misc";
import { buildExecutableCode } from "./Controls";
import { Preview } from "./Preview";
import { setStatus } from "./StatusBar";
import { toast } from "./Toast";

let busyCount = 0;

export const Executor = {
  isBusy: () => busyCount > 0,

  /** 执行指定索引的代码块，结果渲染到预览区 */
  async runBlock(index, source) {
    const block = (state.blocks || []).find((b) => b.index === index);
    if (!block || !block.runnable) {
      setStatus("光标附近没有可执行的代码块");
      toast("该位置附近没有可执行代码块（支持 ```python / ```javascript / ```shell / ```java / ```go）", { kind: "err" });
      return;
    }
    const wrap = document.querySelector(`.nb-block[data-index="${index}"]`);
    const outputEl = wrap && wrap.querySelector(".nb-output");
    const runBtn = wrap && wrap.querySelector(".nb-run");
    if (!outputEl || wrap.dataset.busy) return; // 防重复点击

    wrap.dataset.busy = "1";
    busyCount++;
    syncGlobalRunButtons();
    setButtonRunning(runBtn, true);
    const collect = state.collectors[index];
    const values = collect ? collect() : {};
    const code = Object.keys(values).length
      ? buildExecutableCode(block.language, block.code, values)
      : block.code;
    outputEl.innerHTML = `<span class="nb-running">⏳ ${block.language} 执行中…</span>`;

    try {
      const result = await apiExecute({ language: block.language, code });
      renderResult(outputEl, result);
      Preview.cacheOutput(block.code, outputEl.innerHTML); // FR-09 会话缓存
      const secs = ((result.duration_ms || 0) / 1000).toFixed(2);
      if (result.timed_out) setStatus(`执行超时（${secs} 秒）`, "error");
      else if (result.exit_code === 0) setStatus(`执行完成（${secs} 秒）`, "flash");
      else setStatus(`运行结束，退出码 ${result.exit_code}（${secs} 秒）`, "error");
    } catch (err) {
      const isEnv = err instanceof ApiError && err.code === "ENVIRONMENT_UNAVAILABLE";
      outputEl.innerHTML =
        `<span class="nb-err">❌ ${escapeHtml(err.message || String(err))}</span>`;
      setStatus("运行失败", "error");
      if (isEnv) {
        const hint = err.details?.environment?.hint;
        toast(`<b>${escapeHtml(block.language)}</b> 运行环境未就绪<br/>` +
              `${escapeHtml(hint || "请参考文档安装对应工具链后重试")}`, { kind: "err", ms: 9000 });
      } else {
        toast(`执行请求失败：${escapeHtml(err.message || String(err))}<br/>` +
              `（请确认后端已启动：<code>python backend/app.py</code>）`, { kind: "err", ms: 8000 });
      }
    } finally {
      delete wrap.dataset.busy;
      busyCount = Math.max(0, busyCount - 1);
      syncGlobalRunButtons();
      setButtonRunning(runBtn, false);
    }
  },

  /** 依次执行全部可运行块（调用方负责二次确认） */
  async runAll() {
    const runnable = (state.blocks || []).filter((b) => b.runnable);
    for (const b of runnable) {
      await Executor.runBlock(b.index);
    }
  },
};

function setButtonRunning(btn, on) {
  if (!btn) return;
  btn.disabled = on;
  btn.textContent = on ? "⏳ 运行中…" : "▶ 运行";
}

function syncGlobalRunButtons() {
  const g = document.getElementById("btn-run");
  const ga = document.getElementById("btn-run-all");
  if (g) g.disabled = busyCount > 0;
  if (ga) ga.disabled = busyCount > 0;
}

function renderResult(el, r) {
  const parts = [];
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
