/** 统一请求层（指令文档·八）：解析 {success,data,error} 信封，失败抛 ApiError。
 *
 * 所有组件禁止手写 fetch + 硬编码地址：基址来自 import.meta.env.VITE_API_BASE_URL
 * （开发态为空串 → 走 Vite 代理；生产态同源由 Flask 托管 dist）。
 */
const BASE = import.meta.env.VITE_API_BASE_URL || "";
/** 供非 fetch 场景（如导出下载 <a href>）拼接绝对地址，同样零硬编码。 */
export const API_BASE = BASE;

export class ApiError extends Error {
  constructor(code, message, details) {
    super(message || "请求失败");
    this.code = code || "UNKNOWN";
    this.details = details || null;
  }
}

/** @param {string} path @param {{method?:string, body?:any, rawText?:boolean, headers?:Object}} [opts] */
export async function request(path, opts = {}) {
  const { method = "GET", body, rawText = false, headers = {} } = opts;
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: { ...headers, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("NETWORK", "无法连接本地服务——请确认后端已启动");
  }
  if (rawText) return res.text();
  let j;
  try {
    j = await res.json();
  } catch {
    throw new ApiError("BAD_RESPONSE", `HTTP ${res.status}：响应不是合法 JSON`);
  }
  if (!j || j.success !== true) {
    throw new ApiError(j?.error?.code, j?.error?.message || `HTTP ${res.status}`, j?.error?.details);
  }
  return j.data;
}
