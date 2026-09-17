/** 实时预览渲染（FR-02/04）：可执行代码块升级为 语言徽标 + ▶运行 + 复制 + 控件区 + 输出区。 */
import { marked } from "marked";
import hljs from "highlight.js/lib/common";
import hljsDarkUrl from "highlight.js/styles/github-dark.css?url";
import hljsLightUrl from "highlight.js/styles/github.css?url";

import { state } from "../state";
import { codeHash, debounce, escapeHtml } from "../utils/misc";
import { PARAM_SPEC_LANGS, parseParams, renderControls } from "./Controls";

export const RUNNABLE = new Set([
  "python", "javascript", "js", "shell", "bash", "sh", "java", "go",
]);

/** hljs 配色随主题切换（构建产物 URL，替代旧 CDN 方案） */
export function applyHljsTheme(theme) {
  const link = document.getElementById("hljs-theme");
  if (link) link.href = theme === "light" ? hljsLightUrl : hljsDarkUrl;
}

marked.setOptions({ gfm: true, breaks: false });

export const Preview = {
  /** 渲染 Markdown 到 #preview；onRun(index) 由 App 注入 */
  render(source, onRun) {
    const blocks = extractBlocks(source);
    state.blocks = blocks;
    state.collectors = {};

    const root = document.getElementById("preview");
    root.innerHTML = guardedMarkdown(source);

    // 围栏代码块在 DOM 中按文档顺序出现，与 blocks 一一对应
    root.querySelectorAll("pre").forEach((pre, i) => {
      const block = blocks[i];
      if (!block || !RUNNABLE.has(block.rawLanguage)) return;
      upgradeBlock(pre, block, onRun);
    });

    root.querySelectorAll("pre code").forEach((el) => {
      try { hljs.highlightElement(el); } catch (_) { /* 忽略 */ }
    });

    restoreOutputs(root);
  },

  /** 会话内输出缓存（FR-09 近似）：重渲染后按代码哈希还原 */
  cacheOutput(code, html) {
    state.outputs[codeHash(code)] = html;
  },
};

function upgradeBlock(pre, block, onRun) {
  const wrap = document.createElement("div");
  wrap.className = "nb-block";
  wrap.dataset.index = block.index;
  wrap.dataset.hash = codeHash(block.code);

  const toolbar = document.createElement("div");
  toolbar.className = "nb-toolbar";

  const lang = document.createElement("span");
  lang.className = "nb-lang";
  lang.textContent = block.rawLanguage || "code";

  const runBtn = document.createElement("button");
  runBtn.className = "nb-run";
  runBtn.textContent = "▶ 运行";
  runBtn.setAttribute("aria-label", `运行第 ${block.index + 1} 个代码块`);
  runBtn.addEventListener("click", () => onRun && onRun(block.index));

  const copyBtn = document.createElement("button");
  copyBtn.className = "nb-copy";
  copyBtn.textContent = "复制";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(block.code);
      copyBtn.textContent = "已复制 ✓";
    } catch (_) {
      copyBtn.textContent = "复制失败";
    }
    setTimeout(() => (copyBtn.textContent = "复制"), 1600);
  });

  toolbar.append(lang, runBtn, copyBtn);

  const controls = document.createElement("div");
  controls.className = "nb-controls";

  const output = document.createElement("div");
  output.className = "nb-output";

  wrap.append(toolbar);
  pre.replaceWith(wrap);
  wrap.append(pre, controls, output);

  // 交互控件（FR-07）：值变化 -> 防抖联动执行（FR-08）
  block.params = parseParams(block.code);
  if (block.params.length && PARAM_SPEC_LANGS.has(block.language)) {
    const rerun = debounce(() => onRun && onRun(block.index), 350);
    state.collectors[block.index] = renderControls(controls, block.params, rerun);
  } else {
    block.params = [];
  }
}

function restoreOutputs(root) {
  for (const block of state.blocks || []) {
    const html = state.outputs[codeHash(block.code)];
    if (!html) continue;
    const el = root.querySelector(`.nb-block[data-hash="${codeHash(block.code)}"] .nb-output`);
    if (el && !el.innerHTML) el.innerHTML = html;
  }
}

function guardedMarkdown(source) {
  try {
    return marked.parse(source || "");
  } catch (err) {
    return `<p style="color:var(--err)">预览渲染失败：${escapeHtml(err.message)}</p>`;
  }
}

// ------------------------------------------------------------------
const FENCE_RE = /^ {0,3}(```+|~~~+)\s*([\w+-]*)[^\n]*\n([\s\S]*?)^ {0,3}\1[ \t]*$/gm;
const ALIAS = { js: "javascript", bash: "shell", sh: "shell", py: "python" };

/** 从 Markdown 源码提取代码块（与后端 markdown_parser 规则一致） */
export function extractBlocks(source) {
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
}

/** 找光标处（或其后、否则其前）最近的可执行块 —— Shift+Enter 语义 */
export function blockAtLine(blocks, line) {
  for (const b of blocks) {
    if (b.runnable && b.startLine >= line - 1) return b;
  }
  for (const b of [...blocks].reverse()) {
    if (b.runnable && b.startLine <= line) return b;
  }
  return null;
}
