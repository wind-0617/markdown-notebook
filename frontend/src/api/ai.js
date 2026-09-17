/** AI 对话 API。浏览器端配置（localStorage）随请求 overrides 透传。 */
import { request } from "./client";

export const chat = ({ messages, context = "", ai = null }) =>
  request("/api/ai/chat", { method: "POST", body: { messages, context, ai } });
