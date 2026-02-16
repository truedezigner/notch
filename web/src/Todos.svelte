<script lang="ts">
  import type { Todo } from './api';
  import { createTodo, listTodos, patchTodo, setToken } from './api';

  let todos: Todo[] = [];
  let loading = true;
  let err: string | null = null;

  let newTitle = '';
  let newNotes = '';

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

  async function refresh() {
    loading = true;
    err = null;
    try {
      todos = await listTodos(false);
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
  <button class="ghost" on:click={logout}>Logout</button>
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
        <label class="check">
          <input type="checkbox" checked={t.done} on:change={() => toggle(t)} />
          <span class:done={t.done}>{t.title}</span>
        </label>

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
      </li>
    {/each}
  </ul>
{/if}

<style>
  .top { display:flex; justify-content:space-between; align-items:center; }
  .ghost { background: transparent; border: 1px solid #ddd; border-radius: 10px; padding: 8px 10px; }
  .add { display:flex; flex-direction:column; gap:8px; padding: 12px; border: 1px solid #eee; border-radius: 12px; }
  input, textarea { font: inherit; padding: 10px; border-radius: 10px; border: 1px solid #ccc; }
  textarea { min-height: 70px; resize: vertical; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid #111; background: #111; color: #fff; }
  button:disabled { opacity: .5; }
  .err { margin-top: 10px; color: #b00020; font-size: 13px; }
  .hint { margin-top: 10px; color: #666; font-size: 13px; }
  .list { list-style:none; padding: 0; margin: 12px 0; display:flex; flex-direction:column; gap:10px; }
  .item { border: 1px solid #eee; border-radius: 12px; padding: 12px; }
  .check { display:flex; gap:10px; align-items:center; }
  .done { text-decoration: line-through; color: #777; }
  .notes { margin-left: 28px; margin-top: 6px; color: #333; font-size: 14px; }
  .notes a { color: inherit; text-decoration: underline; }
  .meta { margin-left: 28px; margin-top: 6px; color: #666; font-size: 12px; }
</style>
