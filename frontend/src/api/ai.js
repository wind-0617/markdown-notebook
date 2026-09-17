/** AI API：对话 + 连接测试（功能四）+ 与笔记绑定的聊天记录（功能五）。 */
import { request } from "./client";

const enc = encodeURIComponent;

export const chat = ({ messages, context = "", ai = null }) =>
  request("/api/ai/chat", { method: "POST", body: { messages, context, ai } });

/** 测试连接（不落任何配置，仅验证可用性）。失败按 ApiError 抛出。 */
export const testConnection = (ai) =>
  request("/api/ai/test", { method: "POST", body: ai ? { ai } : {} });

export const loadChat = (note) =>
  request(`/api/ai/chat/${enc(note)}`).then((d) => d.messages || []);
export const saveChat = (note, messages) =>
  request(`/api/ai/chat/${enc(note)}`, { method: "POST", body: { messages } });
export const clearChat = (note) =>
  request(`/api/ai/chat/${enc(note)}`, { method: "DELETE" });
