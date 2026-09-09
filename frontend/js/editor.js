/* ==========================================================================
 * editor.js —— Monaco Editor 初始化与主题联动（FR-01 / FR-04）
 * ========================================================================== */
window.App = window.App || {};

(function () {
  // 资源基址：打包/离线模式为 /vendor（后端重写 index.html 注入），开发态为 CDN
  const MONACO_BASE = window.assetBase() + "/npm/monaco-editor@0.45.0/min";

  /**
   * 创建 Markdown 编辑器。
   * @param {HTMLElement} el 容器
   * @param {string} value 初始内容
   * @param {string} theme 'dark' | 'light'
   */
  App.createEditor = function (el, value, theme) {
    return new Promise((resolve, reject) => {
      if (!window.require) {
        reject(new Error("Monaco loader 未加载（检查网络/CDN）"));
        return;
      }
      // 跨域 CDN 的 Web Worker 需要用 data-url 中转
      window.MonacoEnvironment = {
        getWorkerUrl: function () {
          const src = `importScripts('${MONACO_BASE}/vs/base/worker/workerMain.js');`;
          return URL.createObjectURL(new Blob([src], { type: "text/javascript" }));
        },
      };
      window.require.config({ paths: { vs: MONACO_BASE + "/vs" } });
      window.require(["vs/editor/editor.main"], function () {
        monaco.editor.defineTheme("nb-dark", {
          base: "vs-dark", inherit: true,
          rules: [],
          colors: { "editor.background": "#0e1117" },
        });
        const editor = monaco.editor.create(el, {
          value: value || "",
          language: "markdown",
          theme: theme === "light" ? "vs" : "nb-dark",
          automaticLayout: true,
          wordWrap: "on",
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: '"JetBrains Mono", "Cascadia Code", Consolas, "Microsoft YaHei", monospace',
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          renderLineHighlight: "all",
          smoothScrolling: true,
          cursorBlinking: "smooth",
          tabSize: 2,
        });
        resolve(editor);
      }, reject);
    });
  };

  /** 主题切换联动 Monaco */
  App.applyMonacoTheme = function (theme) {
    if (!window.monaco) return;
    monaco.editor.setTheme(theme === "light" ? "vs" : "nb-dark");
  };

  /** 光标位置（1 起行号），供 Shift+Enter 定位代码块 */
  App.cursorLine = function (editor) {
    return editor.getPosition() ? editor.getPosition().lineNumber : 1;
  };
})();
