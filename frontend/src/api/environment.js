/** 系统 / 环境探测 API。 */
import { request } from "./client";

export const health = () => request("/api/health");
export const checkEnv = (lang) => request(`/api/environment/check?lang=${encodeURIComponent(lang)}`);
