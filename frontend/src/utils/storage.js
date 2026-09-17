/** localStorage 统一封装：异常安全 + AI 配置专用存取（功能四）。
 *
 * 键名沿用 v0.3 的 nb.ai.settings —— 老用户已有配置零迁移。
 */
const AI_CFG_KEY = "nb.ai.…s";

export function lsGet(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (_) {
    return fallback;
  }
}

export function lsSet(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; }
  catch (_) { return false; }   // 隐私模式/配额满：功能降级不崩
}

export function lsRemove(key) {
  try { localStorage.removeItem(key); } catch (_) { /* 忽略 */ }
}

export const loadAiConfig = () => lsGet(AI_CFG_KEY, {}) || {};
export const saveAiConfig = (cfg) => lsSet(AI_CFG_KEY, cfg);
export const clearAiConfig = () => lsRemove(AI_CFG_KEY);

/** base+model 必填；非本机地址还需要 Key（与后端校验口径一致） */
export function aiConfigUsable(cfg) {
  const base = (cfg.base_url || "").trim();
  const model = (cfg.model || "").trim();
  const key = (cfg.api_key || "").trim();
  if (!base || !model) return false;
  if (/localhost|127\.0\.0\.1/i.test(base)) return true;
  return !!key;
}
