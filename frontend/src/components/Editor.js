/** Monaco 编辑器封装（FR-01/04/06）：npm 依赖 ESM 直连，仅编辑器基础 worker。
 *
 * 本模块被 App.js 动态 import —— Monaco 体积大，随编辑器就绪再进主 bundle 分片。
 */
import * as monaco from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };

monaco.editor.defineTheme("nb-dark", {
  base: "vs-dark",
  inherit: true,
  rules: [],
  colors: { "editor.background": "#0e1117" },
});

/**
 * 创建 Markdown 编辑器并注册编辑器内快捷键。
 * @param {HTMLElement} el 容器
 * @param {{value:string, theme:string, onSave:Function, onRunAtCursor:Function}} opts
 */
export function createEditor(el, opts) {
  const { value, theme, onSave, onRunAtCursor } = opts;
  el.innerHTML = ""; // 清除"加载编辑器…"占位，避免与 Monaco 叠层
  const editor = monaco.editor.create(el, {
    value: value || "",
    language: "markdown",
    theme: theme === "light" ? "vs" : "nb-dark",
    automaticLayout: true,
    wordWrap: "on",
    minimap: { enabled: false },
    fontSize: 14,
    fontFamily:
      '"JetBrains Mono", "Cascadia Code", Consolas, "Microsoft YaHei", monospace',
    lineNumbers: "on",
    scrollBeyondLastLine: false,
    renderLineHighlight: "all",
    smoothScrolling: true,
    cursorBlinking: "smooth",
    tabSize: 2,
  });

  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => onSave());
  editor.addCommand(monaco.KeyMod.Shift | monaco.KeyCode.Enter, () => onRunAtCursor());
  return editor;
}

export function applyMonacoTheme(theme) {
  monaco.editor.setTheme(theme === "light" ? "vs" : "nb-dark");
}

/** 光标 1 起行号，供 Shift+Enter 定位代码块 */
export function cursorLine(editor) {
  const p = editor.getPosition();
  return p ? p.lineNumber : 1;
}
