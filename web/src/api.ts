export type User = { id: string; handle: string; display_name: string };
export type Todo = {
  id: string;
  title: string;
  notes?: string | null;
  done: boolean;
  due_at?: number | null;
  remind_at?: number | null;
  remind_sent_at?: number | null;
  assigned_to?: string | null;
  shared_with: string[];
  created_by: string;
  created_at: number;
  updated_at: number;
  version: number;
};

const TOKEN_KEY = 'notch_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string | null) {
  if (!t) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, t);
}

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

export async function login(handle: string, password: string): Promise<{ token: string; user: User }> {
  const j = await req('/api/auth/login', { method: 'POST', body: JSON.stringify({ handle, password }) });
  return { token: j.token, user: j.user };
}

export async function me(): Promise<User> {
  const j = await req('/api/me');
  return j.user;
}

export async function listUsers(): Promise<User[]> {
  const j = await req('/api/users');
  return j.users;
}

export async function listTodos(includeDone = false): Promise<Todo[]> {
  const j = await req(`/api/todos?include_done=${includeDone ? 1 : 0}`);
  return j.todos;
}

export async function createTodo(title: string, notes?: string): Promise<Todo> {
  const j = await req('/api/todos', { method: 'POST', body: JSON.stringify({ title, notes }) });
  return j.todo;
}

export async function patchTodo(id: string, patch: any): Promise<Todo> {
  const j = await req(`/api/todos/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
  return j.todo;
}
