<script lang="ts">
  import type { Todo } from './api';
  import { createTodo, listTodos, patchTodo, setToken } from './api';

  import type { User } from './api';
  import { listUsers } from './api';

  let todos: Todo[] = [];
  let users: User[] = [];
  let loading = true;
  let err: string | null = null;

  let newTitle = '';
  let newNotes = '';
  let includeDone = false;
  export let initialExpandedId: string | null = null;
  let expandedId: string | null = null;

  function fmtTime(ts?: number | null) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  }

  function renderNotes(s?: string | null): { text: string; url?: string }[] {
    const t = (s || '').trim();
    if (!t) return [];
    const re = /(https?:\/\/\S+)/g;
    const parts: { text: string; url?: string }[] = [];
    let last = 0;
    for (const m of t.matchAll(re)) {
      const idx = m.index ?? 0;
      if (idx > last) parts.push({ text: t.slice(last, idx) });
      const url = m[0];
      parts.push({ text: '(link)', url });
      last = idx + url.length;
    }
    if (last < t.length) parts.push({ text: t.slice(last) });
    return parts;
  }

  function userLabel(id?: string | null) {
    if (!id) return '';
    const u = users.find(u => u.id === id);
    return u ? u.display_name : '';
  }

  function toLocalInput(ts?: number | null) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function fromLocalInput(v: string): number | null {
    const s = (v || '').trim();
    if (!s) return null;
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return null;
    return Math.floor(d.getTime() / 1000);
  }

  async function refresh() {
    loading = true;
    err = null;
    try {
      // load users first for assignee labels
      users = await listUsers();
      todos = await listTodos(includeDone);
      if (initialExpandedId) {
        const found = todos.find(t => t.id === initialExpandedId);
        if (found) expandedId = initialExpandedId;
      }
    } catch (e: any) {
      err = e?.message || String(e);
    } finally {
      loading = false;
    }
  }

  async function add() {
    const title = newTitle.trim();
    if (!title) return;
    try {
      const t = await createTodo(title, newNotes.trim() || undefined);
      todos = [t, ...todos];
      newTitle = '';
      newNotes = '';
    } catch (e: any) {
      err = e?.message || String(e);
    }
  }

  async function toggle(todo: Todo) {
    const desired = !todo.done;
    // optimistic
    todo.done = desired;
    try {
      const updated = await patchTodo(todo.id, { done: desired, if_version: todo.version });
      todos = todos.map(t => (t.id === updated.id ? updated : t));
    } catch (e: any) {
      err = e?.message || String(e);
      await refresh();
    }
  }

  function logout() {
    setToken(null);
    location.reload();
  }

  refresh();
</script>

<div class="top">
  <h3>Todos</h3>
  <div class="topRight">
    <label class="toggle"><input type="checkbox" bind:checked={includeDone} on:change={refresh} /> Show done</label>
    <button class="logout" on:click={logout} title="Log out">Log out</button>
  </div>
</div>

<div class="add">
  <input bind:value={newTitle} placeholder="New reminder…" on:keydown={(e) => e.key === 'Enter' && add()} />
  <textarea bind:value={newNotes} placeholder="Optional notes (URLs become (link))"></textarea>
  <button on:click={add} disabled={!newTitle.trim()}>Add</button>
</div>

{#if err}
  <div class="err">{err}</div>
{/if}

{#if loading}
  <div class="hint">Loading…</div>
{:else}
  <ul class="list">
    {#each todos as t (t.id)}
      <li class="item">
        <div class="row1">
          <label class="check">
            <input type="checkbox" checked={t.done} on:change={() => toggle(t)} />
            <button type="button" class:done={t.done} class="titleBtn" on:click={() => {
              expandedId = expandedId === t.id ? null : t.id;
              // update URL for deep-linking
              const base = location.pathname.includes('/app/') ? '/app/' : '/';
              const next = expandedId ? `${base}todos/${encodeURIComponent(t.id)}` : `${base}`;
              history.pushState({}, '', next);
            }}>{t.title}</button>
          </label>
          {#if t.assigned_to}
            <span class="pill">{userLabel(t.assigned_to)}</span>
          {/if}
        </div>

        {#if t.notes}
          <div class="notes">
            {#each renderNotes(t.notes) as p}
              {#if p.url}
                <a href={p.url} target="_blank" rel="noreferrer">{p.text}</a>
              {:else}
                <span>{p.text}</span>
              {/if}
            {/each}
          </div>
        {/if}

        {#if t.remind_at}
          <div class="meta">Remind: {fmtTime(t.remind_at)}</div>
        {/if}

        {#if expandedId === t.id}
          <div class="editor">
            <div class="field">
              <label for={`assign-${t.id}`}>Assign</label>
              <select id={`assign-${t.id}`} value={t.assigned_to || ''} on:change={async (e) => {
                const v = (e.currentTarget as HTMLSelectElement).value;
                try {
                  const updated = await patchTodo(t.id, { assigned_to: v || null, if_version: t.version });
                  todos = todos.map(x => x.id === updated.id ? updated : x);
                } catch (err2:any) { err = err2?.message || String(err2); await refresh(); }
              }}>
                <option value="">Unassigned</option>
                {#each users as u}
                  <option value={u.id}>{u.display_name}</option>
                {/each}
              </select>
            </div>

            <div class="field">
              <label for={`remind-${t.id}`}>Remind</label>
              <input id={`remind-${t.id}`} type="datetime-local" value={toLocalInput(t.remind_at)} on:change={async (e) => {
                const v = (e.currentTarget as HTMLInputElement).value;
                const ts = fromLocalInput(v);
                try {
                  const updated = await patchTodo(t.id, { remind_at: ts, if_version: t.version });
                  todos = todos.map(x => x.id === updated.id ? updated : x);
                } catch (err2:any) { err = err2?.message || String(err2); await refresh(); }
              }} />
            </div>
          </div>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .top { display:flex; justify-content:space-between; align-items:center; gap: 10px; }
  .topRight { display:flex; align-items:center; gap:10px; }
  .toggle { font-size: 12px; color: var(--muted); display:flex; gap:6px; align-items:center; }
  .logout { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; font-weight: 800; color: var(--text); }
  .logout:hover { filter: brightness(1.08); }
  .add { display:flex; flex-direction:column; gap:8px; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--panel); }
  input, textarea { font: inherit; padding: 10px; border-radius: 10px; }
  textarea { min-height: 70px; resize: vertical; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); font-weight: 800; }
  button:disabled { opacity: .5; }
  .err { margin-top: 10px; color: var(--danger); font-size: 13px; }
  .hint { margin-top: 10px; color: var(--muted); font-size: 13px; }
  .list { list-style:none; padding: 0; margin: 12px 0; display:flex; flex-direction:column; gap:10px; }
  .item { border: 1px solid var(--border); border-radius: 12px; padding: 12px; background: var(--panel); }
  .row1 { display:flex; justify-content:space-between; align-items:center; gap:10px; }
  .check { display:flex; gap:10px; align-items:center; }
  .titleBtn { cursor: pointer; background: transparent; border: none; padding: 0; text-align:left; font: inherit; color: var(--text); }
  .titleBtn:hover { text-decoration: underline; }
  .pill { font-size: 12px; border: 1px solid var(--border); border-radius: 999px; padding: 2px 8px; color: var(--muted); }
  .editor { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--border); display:flex; gap: 10px; flex-wrap: wrap; }
  .field { display:flex; flex-direction:column; gap: 6px; }
  .field label { font-size: 12px; color: var(--muted); }
  select { padding: 10px; border-radius: 10px; min-width: 180px; }
  .done { text-decoration: line-through; color: var(--muted); }
  .notes { margin-left: 28px; margin-top: 6px; color: var(--text); font-size: 14px; opacity: 0.9; }
  .notes a { color: inherit; text-decoration: underline; }
  .meta { margin-left: 28px; margin-top: 6px; color: var(--muted); font-size: 12px; }
</style>
