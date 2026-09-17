/** 跨组件共享状态（单一事实源，模块图内直接引用）。 */
export const state = {
  editor: null, // Monaco 实例（Editor.js 惰性创建）
  fileName: null, // 当前笔记名（null = 未命名）
  dirty: false,
  blocks: [], // 解析出的代码块 [{index, language, code, params, runnable, startLine, endLine}]
  collectors: {}, // blockIndex -> 参数控件 value getter
  outputs: {}, // blockIndex -> {stdout, stderr, exit_code, ...} 供重渲染还原
  env: {}, // language -> {available, version, hint}
  aiConfigured: false,
  theme: "dark",
};

export function setDirty(v) {
  if (state.dirty === v) return;
  state.dirty = v;
  const dot = document.getElementById("file-tab-dirty");
  if (dot) dot.classList.toggle("hidden", !v);
  const sd = document.getElementById("status-dirty");
  if (sd) sd.textContent = v ? "未保存" : "";
}
