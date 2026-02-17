export type User = { id: string; handle: string; display_name: string; is_admin?: boolean };
export type Todo = {
  id: string;
  list_id?: string | null;
  title: string;
  // (No description/notes field for todos)
  __deprecated_notes?: never;
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

export async function adminCreateUser(handle: string, password: string, display_name?: string): Promise<User> {
  const j = await req('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify({ handle, password, display_name })
  });
  return j.user as User;
}

export type TodoList = { id: string; name: string; created_by: string; shared_with: string[]; created_at: number; updated_at: number };

export async function listLists(): Promise<TodoList[]> {
  const j = await req('/api/lists');
  return j.lists;
}

export async function createList(name: string): Promise<TodoList> {
  const j = await req('/api/lists', { method: 'POST', body: JSON.stringify({ name }) });
  return j.list;
}

export async function listTodos(includeDone = false, listId?: string | null, opts: { deleted_only?: boolean } = {}): Promise<Todo[]> {
  const qs = new URLSearchParams();
  qs.set('include_done', includeDone ? '1' : '0');
  if (listId) qs.set('list_id', listId);
  if (opts.deleted_only) {
    qs.set('include_deleted', '1');
    qs.set('deleted_only', '1');
  }
  const j = await req(`/api/todos?${qs.toString()}`);
  return j.todos;
}

export async function createTodo(title: string, listId?: string | null): Promise<Todo> {
  const body: any = { title };
  if (listId) body.list_id = listId;
  const j = await req('/api/todos', { method: 'POST', body: JSON.stringify(body) });
  return j.todo;
}

export async function patchTodo(id: string, patch: any): Promise<Todo> {
  const j = await req(`/api/todos/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
  return j.todo;
}

export async function deleteTodo(id: string): Promise<{ ok: boolean; deleted: boolean; id: string }> {
  const j = await req(`/api/todos/${encodeURIComponent(id)}`, { method: 'DELETE' });
  return j;
}

export async function restoreTodo(id: string): Promise<Todo> {
  const j = await req(`/api/todos/${encodeURIComponent(id)}/restore`, { method: 'POST' });
  return j.todo as Todo;
}
