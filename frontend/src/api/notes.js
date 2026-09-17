/** 笔记资源 API（/api/notes）。 */
import { request, API_BASE } from "./client";

const enc = encodeURIComponent;

export const listNotes = () => request("/api/notes").then((d) => d.notes);
export const readNote = (name) => request(`/api/notes/${enc(name)}`);
export const createNote = (name, content) =>
  request("/api/notes", { method: "POST", body: { name, content } });
export const saveNote = (name, content) =>
  request(`/api/notes/${enc(name)}`, { method: "PUT", body: { content } });
export const deleteNote = (name) => request(`/api/notes/${enc(name)}`, { method: "DELETE" });
/** 重命名（功能一）：newName 可不含 .md 后缀，服务端补全并校验 */
export const renameNote = (oldPath, newName) =>
  request("/api/notes/rename", { method: "POST", body: { old_path: oldPath, new_name: newName } });
/** 导出（功能三）：返回浏览器原生下载地址（attachment 流），不走 fetch */
export const exportNoteUrl = (name) => `${API_BASE}/api/notes/${enc(name)}/export`;
