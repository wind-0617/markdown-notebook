/** 执行 / 渲染 / 解析 API。 */
import { request } from "./client";

export const execute = (payload) => request("/api/execute", { method: "POST", body: payload });
export const renderMarkdown = (markdown) => request("/api/render", { method: "POST", body: { markdown } });
export const parseMarkdown = (markdown) => request("/api/parse", { method: "POST", body: { markdown } });
