import { getToken } from './api';

export type NoteGroup = {
  id: string;
  name: string;
  created_by: string;
  shared_with: string[];
  created_at: number;
  updated_at: number;
};

export type Note = {
  id: string;
  group_id?: string | null;
  title: string;
  body_md: string;
  shared_with: string[];
  created_by: string;
  created_at: number;
  updated_at: number;
  version: number;
};

async function req(path: string, opts: RequestInit = {}) {
  const token = getToken();
  const headers: any = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { ...opts, headers });
  const text = await res.text();

  let json: any = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* ignore */
  }

  if (!res.ok) {
    const detail = json?.detail || text || res.statusText;
    throw new Error(detail);
  }

  return json;
}

export async function listNoteGroups(): Promise<NoteGroup[]> {
  const j = await req('/api/note-groups');
  return j.groups as NoteGroup[];
}

export async function createNoteGroup(name: string, shared_with: string[] = []): Promise<NoteGroup> {
  const j = await req('/api/note-groups', {
    method: 'POST',
    body: JSON.stringify({ name, shared_with })
  });
  return j.group as NoteGroup;
}

export async function patchNoteGroup(id: string, patch: any): Promise<NoteGroup> {
  const j = await req(`/api/note-groups/${encodeURIComponent(id)}`,
    { method: 'PATCH', body: JSON.stringify(patch) }
  );
  return j.group as NoteGroup;
}

export async function listNotes(group_id?: string | null, query?: string | null, limit = 200): Promise<Note[]> {
  const qs = new URLSearchParams();
  if (group_id) qs.set('group_id', group_id);
  if (query) qs.set('query', query);
  if (limit) qs.set('limit', String(limit));
  const j = await req(`/api/notes?${qs.toString()}`);
  return j.notes as Note[];
}

export async function createNote(title: string, group_id?: string | null, body_md = ''): Promise<Note> {
  const payload: any = { title, body_md };
  if (group_id) payload.group_id = group_id;
  const j = await req('/api/notes', { method: 'POST', body: JSON.stringify(payload) });
  return j.note as Note;
}

export async function getNote(id: string): Promise<Note> {
  const j = await req(`/api/notes/${encodeURIComponent(id)}`);
  return j.note as Note;
}

export async function patchNote(id: string, patch: any): Promise<Note> {
  const j = await req(`/api/notes/${encodeURIComponent(id)}`,
    { method: 'PATCH', body: JSON.stringify(patch) }
  );
  return j.note as Note;
}

export async function deleteNote(id: string): Promise<{ ok: boolean; deleted: boolean; id: string }> {
  const j = await req(`/api/notes/${encodeURIComponent(id)}`, { method: 'DELETE' });
  return j;
}

export async function createNoteShare(id: string, opts: { can_edit?: boolean; expires_in_seconds?: number | null } = {}): Promise<{ ok: boolean; token: string; url: string; can_edit: boolean; expires_at?: number | null; note_id: string }> {
  const j = await req(`/api/notes/${encodeURIComponent(id)}/share`, {
    method: 'POST',
    body: JSON.stringify(opts || {})
  });
  return j;
}
