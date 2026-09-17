/** 笔记资源 API（/api/notes）。 */
import { request } from "./client";

const enc = encodeURIComponent;

export const listNotes = () => request("/api/notes").then((d) => d.notes);
export const readNote = (name) => request(`/api/notes/${enc(name)}`);
export const createNote = (name, content) =>
  request("/api/notes", { method: "POST", body: { name, content } });
export const saveNote = (name, content) =>
  request(`/api/notes/${enc(name)}`, { method: "PUT", body: { content } });
export const deleteNote = (name) => request(`/api/notes/${enc(name)}`, { method: "DELETE" });
