/** 全局快捷键绑定（FR-06 + 九.2 的 Ctrl+K）。编辑器内的组合键由 Monaco addCommand 处理。 */
export function bindGlobalShortcuts({ onSave, onSearchFocus }) {
  document.addEventListener("keydown", (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    if (e.key.toLowerCase() === "s") {
      e.preventDefault();
      onSave();
    } else if (e.key.toLowerCase() === "k") {
      e.preventDefault();
      onSearchFocus();
    }
  });
}
