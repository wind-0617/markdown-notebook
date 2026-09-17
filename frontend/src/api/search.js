/** 全文检索 API（Whoosh 后端）。 */
import { request } from "./client";

export const search = (q) => request(`/api/search?q=${encodeURIComponent(q)}`);
export const rebuildIndex = () => request("/api/search/rebuild", { method: "POST" });
