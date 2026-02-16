import type { User } from './api';
import { getToken } from './api';

export type NoteGroup = { id: string; name: string; created_by: string; shared_with: string[]; created_at: number; updated_at: number };
export type Note = { id: string; group_id?: string | null; title: string; body_md: string; shared_with: string[]; created_by: string; created_at: number; updated_at: number; version: number };

async function req(path: string, opts: RequestInit = {}) {
  const token = getToken();
  const headers: any = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { ...opts, headers });
  const text = await res.text();
  let json: any = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* ignore */ }
  if (!res.ok) {
    const detail = json?.detail || text || res.statusText;
    throw new Error(detail);
  }
  return json;
}

export async function listUsers(): Promise<User[]> {
  const j = await req('/api/users');
  return j.users;
}

export async function listNoteGroups(): Promise<NoteGroup[]> {
  const j = await req('/api/note-groups');
  return j.groups;
}

export async function createNoteGroup(name: string): Promise<NoteGroup> {
  const j = await req('/api/note-groups', { method: 'POST', body: JSON.stringify({ name }) });
  return j.group;
}

export async function listNotes(groupId?: string | null): Promise<Note[]> {
  const qs = new URLSearchParams();
  if (groupId) qs.set('group_id', groupId);
  const j = await req(`/api/notes?${qs.toString()}`);
  return j.notes;
}

export async function createNote(title: string, groupId?: string | null): Promise<Note> {
  const body: any = { title, body_md: '' };
  if (groupId) body.group_id = groupId;
  const j = await req('/api/notes', { method: 'POST', body: JSON.stringify(body) });
  return j.note;
}

export async function patchNote(id: string, patch: any): Promise<Note> {
  const j = await req(`/api/notes/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
  return j.note;
}
