/* ==========================================================================
 * preview.js —— 实时预览渲染（FR-02 / FR-04）
 * 可执行代码块升级为：语言徽标 + ▶运行 + 复制 + 控件区 + 输出区。
 * ========================================================================== */
window.App = window.App || {};

(function () {
  const RUNNABLE = new Set(["python", "javascript", "js", "shell", "bash", "sh"]);

  App.Preview = {
    blocks: [],
    outputs: {},        // codeHash -> 输出 HTML（FR-09 的前端近似实现）
    collectors: {},     // blockIndex -> () => 参数值

    /** 渲染 Markdown 到 #preview；onRun(index) 由 app.js 注入 */
    render: function (source, onRun) {
      const blocks = App.extractBlocks(source);
      this.blocks = blocks;
      this.collectors = {};

      const root = document.getElementById("preview");
      marked.setOptions({ gfm: true, breaks: false });
      root.innerHTML = guardedMarkdown(source);

      // 围栏代码块在 DOM 中按文档顺序出现，与 blocks 一一对应
      root.querySelectorAll("pre").forEach((pre, i) => {
        const block = blocks[i];
        if (!block || !RUNNABLE.has(block.rawLanguage)) return;
        upgradeBlock(pre, block, onRun);
      });

      root.querySelectorAll("pre code").forEach((el) => {
        try { window.hljs && hljs.highlightElement(el); } catch (_) { /* 忽略 */ }
      });

      restoreOutputs(root);
    },

    cacheOutput: function (code, html) {
      this.outputs[App.codeHash(code)] = html;
    },
  };

  /** 把一个 <pre> 升级为可执行块 */
  function upgradeBlock(pre, block, onRun) {
    const wrap = document.createElement("div");
    wrap.className = "nb-block";
    wrap.dataset.index = block.index;
    wrap.dataset.hash = App.codeHash(block.code);

    // 工具条：语言徽标 + 运行 + 复制（语言标注来自围栏本身，无全局选择器）
    const toolbar = document.createElement("div");
    toolbar.className = "nb-toolbar";

    const lang = document.createElement("span");
    lang.className = "nb-lang";
    lang.textContent = block.rawLanguage || "code";

    const runBtn = document.createElement("button");
    runBtn.className = "nb-run";
    runBtn.textContent = "▶ 运行";
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
    block.params = App.parseParams(block.code);
    if (block.params.length) {
      const rerun = App.debounce(() => onRun && onRun(block.index), 350);
      const collect = App.renderControls(controls, block.params, rerun);
      App.Preview.collectors[block.index] = collect;
    }
  }

  /** 重渲染后，按代码内容哈希恢复上次执行结果 */
  function restoreOutputs(root) {
    for (const block of App.Preview.blocks || []) {
      const html = App.Preview.outputs[App.codeHash(block.code)];
      if (!html) continue;
      const el = root.querySelector(`.nb-block[data-hash="${App.codeHash(block.code)}"] .nb-output`);
      if (el && !el.innerHTML) el.innerHTML = html;
    }
  }

  /** 渲染 Markdown；捕获异常避免输入卡顿（NFR-02） */
  function guardedMarkdown(source) {
    try {
      return marked.parse(source || "");
    } catch (err) {
      return `<p style="color:var(--err)">预览渲染失败：${err.message}</p>`;
    }
  }

  /** djb2 哈希，用于前端输出缓存键 */
  App.codeHash = function (code) {
    let h = 5381;
    for (let i = 0; i < code.length; i++) h = ((h << 5) + h + code.charCodeAt(i)) >>> 0;
    return "h" + h.toString(36);
  };

  /** 简易防抖：返回延迟执行的包装函数 */
  App.debounce = function (fn, wait) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  };
})();
