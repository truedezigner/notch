<script lang="ts">
  import type { Todo, TodoList } from './api';
  import { createTodo, createList, listLists, listTodos, patchTodo, deleteTodo, restoreTodo, setToken } from './api';

  import type { User } from './api';
  import { listUsers } from './api';

  let todos: Todo[] = [];
  let users: User[] = [];
  let lists: TodoList[] = [];
  // '' means "All lists"; '__trash__' means Trash
  let activeListId: string = '';

  let loading = true;
  let err: string | null = null;

  let newListName = '';
  let newTitle = '';
  let includeDone = false;
  export let initialExpandedId: string | null = null;
  let expandedId: string | null = null;

  let toast: { msg: string; action?: string; fn?: () => void } | null = null;
  let toastTimer: any = null;
  function showToast(t: { msg: string; action?: string; fn?: () => void }) {
    toast = t;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast = null; toastTimer = null; }, 5500);
  }

  function listLabel(id?: string | null) {
    if (!id) return '';
    const l = lists.find(x => x.id === id);
    return l ? l.name : '';
  }

  function fmtTime(ts?: number | null) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  }

  // Todos intentionally have no description/notes field (Reminders-style title-only).

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
      users = await listUsers();
      lists = await listLists();
      // Default to All lists so shared todos show up even if their list isn't shared.
      const trash = activeListId === '__trash__';
      todos = await listTodos(includeDone, trash ? null : (activeListId || null), { deleted_only: trash });
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

  async function addList() {
    const name = newListName.trim();
    if (!name) return;
    try {
      const lst = await createList(name);
      lists = [...lists, lst].sort((a,b)=>a.name.localeCompare(b.name));
      activeListId = lst.id;
      newListName = '';
      await refresh();
    } catch (e: any) {
      err = e?.message || String(e);
    }
  }

  async function add() {
    const title = newTitle.trim();
    if (!title) return;
    try {
      const t = await createTodo(title, activeListId || null);
      todos = [t, ...todos];
      newTitle = '';
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

{#if toast}
  <div class="toast" role="status">
    <div class="toastMsg">{toast.msg}</div>
    {#if toast.action && toast.fn}
      <button class="toastBtn" type="button" on:click={() => { const fn = toast?.fn; toast = null; fn && fn(); }}> {toast.action} </button>
    {/if}
  </div>
{/if}

<div class="top">
  <div class="topLeft">
    <h3>Todos</h3>
    <select class="listSel" bind:value={activeListId} on:change={refresh}>
      <option value="">All</option>
      <option value="__trash__">Trash</option>
      {#each lists as l}
        <option value={l.id}>{l.name}</option>
      {/each}
    </select>
  </div>
  <div class="topRight">
    <label class="toggle"><input type="checkbox" bind:checked={includeDone} on:change={refresh} /> Show done</label>
    <button class="logout" on:click={logout} title="Log out">Log out</button>
  </div>
</div>

<div class="addList">
  <input bind:value={newListName} placeholder="New list…" on:keydown={(e) => e.key === 'Enter' && addList()} />
  <button on:click={addList} disabled={!newListName.trim()}>Add list</button>
</div>

<div class="add">
  <input bind:value={newTitle} placeholder="New reminder…" on:keydown={(e) => e.key === 'Enter' && add()} />
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

          <div class="right">
            {#if t.assigned_to}
              <span class="pill">{userLabel(t.assigned_to)}</span>
            {/if}

            {#if !activeListId && t.list_id}
              <span class="pill">{listLabel(t.list_id)}</span>
            {/if}

            {#if expandedId === t.id}
              <button class="iconBtn" type="button" title="Copy link" aria-label="Copy link" on:click={async ()=>{
                const base = location.pathname.includes('/app/') ? '/app/' : '/';
                const url = `${location.origin}${base}todos/${encodeURIComponent(t.id)}`;
                try {
                  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') await navigator.clipboard.writeText(url);
                  else {
                    const ta = document.createElement('textarea');
                    ta.value = url;
                    ta.style.position = 'fixed';
                    ta.style.left = '-9999px';
                    ta.style.top = '0';
                    document.body.appendChild(ta);
                    ta.focus();
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                  }
                }
                catch (e:any) { prompt('Copy this:', url); }
              }}>
                <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
                  <path fill="currentColor" d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3ZM5 5h6v2H7v10h10v-4h2v6H5V5Z" />
                </svg>
              </button>

              <button class="trash" type="button" on:click={async () => {
                if (!confirm('Move this todo to trash?')) return;
                try {
                  await deleteTodo(t.id);
                  expandedId = null;
                  showToast({
                    msg: 'Moved to Trash',
                    action: 'Undo',
                    fn: async () => { try { await restoreTodo(t.id); await refresh(); } catch (e2:any) { err = e2?.message || String(e2); } }
                  });
                  await refresh();
                } catch (err2:any) { err = err2?.message || String(err2); }
              }}>Trash</button>
            {/if}
          </div>
        </div>

        <!-- Todos are title-only (no description field). -->

        {#if t.due_at}
          <div class="meta">Due: {fmtTime(t.due_at)}</div>
        {/if}
        {#if t.remind_at}
          <div class="meta">Remind: {fmtTime(t.remind_at)}</div>
        {/if}

        {#if expandedId === t.id}
          <div class="editor">
            <div class="field">
              <label for={`title-${t.id}`}>Title</label>
              <input id={`title-${t.id}`} value={t.title} on:change={async (e)=>{
                const v = (e.currentTarget as HTMLInputElement).value;
                try {
                  const updated = await patchTodo(t.id, { title: v, if_version: t.version });
                  todos = todos.map(x => x.id === updated.id ? updated : x);
                } catch (err2:any) { err = err2?.message || String(err2); await refresh(); }
              }} />
            </div>

            <div class="field">
              <label for={`move-${t.id}`}>List</label>
              <select id={`move-${t.id}`} value={t.list_id || ''} on:change={async (e)=>{
                const v = (e.currentTarget as HTMLSelectElement).value;
                try {
                  const updated = await patchTodo(t.id, { list_id: v || null, if_version: t.version });
                  todos = todos.map(x => x.id === updated.id ? updated : x);
                  // If moved away from current list, refresh the current list view.
                  await refresh();
                } catch (err2:any) { err = err2?.message || String(err2); await refresh(); }
              }}>
                {#each lists as l}
                  <option value={l.id}>{l.name}</option>
                {/each}
              </select>
            </div>

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
              <div class="label">Shared with</div>
              <div class="shareBox">
                {#each users as u}
                  <label class="shareRow">
                    <input type="checkbox" checked={t.shared_with?.includes(u.id)} on:change={async (e) => {
                      const checked = (e.currentTarget as HTMLInputElement).checked;
                      const next = new Set(t.shared_with || []);
                      if (checked) next.add(u.id); else next.delete(u.id);
                      try {
                        const updated = await patchTodo(t.id, { shared_with: Array.from(next), if_version: t.version });
                        todos = todos.map(x => x.id === updated.id ? updated : x);
                      } catch (err2:any) { err = err2?.message || String(err2); await refresh(); }
                    }} />
                    <span>{u.display_name}</span>
                  </label>
                {/each}
              </div>
            </div>

            <div class="field">
              <label for={`due-${t.id}`}>Due</label>
              <input id={`due-${t.id}`} type="datetime-local" value={toLocalInput(t.due_at)} on:change={async (e) => {
                const v = (e.currentTarget as HTMLInputElement).value;
                const ts = fromLocalInput(v);
                try {
                  const updated = await patchTodo(t.id, { due_at: ts, if_version: t.version });
                  todos = todos.map(x => x.id === updated.id ? updated : x);
                } catch (err2:any) { err = err2?.message || String(err2); await refresh(); }
              }} />
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
  .top { display:flex; justify-content:space-between; align-items:center; gap: 10px; flex-wrap: wrap; }
  .topLeft { display:flex; align-items:center; gap: 10px; }
  .topRight { display:flex; align-items:center; gap:10px; }
  .listSel { padding: 8px 10px; border-radius: 10px; }
  .toggle { font-size: 12px; color: var(--muted); display:flex; gap:6px; align-items:center; }
  .logout { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; font-weight: 800; color: var(--text); }
  .logout:hover { filter: brightness(1.08); }
  .addList { display:flex; gap:8px; align-items:center; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--panel); margin-top: 10px; }
.addList input { flex: 1; }
.add { display:flex; flex-direction:column; gap:8px; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--panel); margin-top: 10px; }
  input { font: inherit; padding: 10px; border-radius: 10px; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); font-weight: 800; }
  button:disabled { opacity: .5; }
  .err { margin-top: 10px; color: var(--danger); font-size: 13px; }
  .hint { margin-top: 10px; color: var(--muted); font-size: 13px; }
  .list { list-style:none; padding: 0; margin: 12px 0; display:flex; flex-direction:column; gap:10px; }
  .item { border: 1px solid var(--border); border-radius: 12px; padding: 12px; background: var(--panel); }
  .row1 { display:flex; justify-content:space-between; align-items:center; gap:10px; }
  .right { display:flex; align-items:center; gap:8px; }
  .check { display:flex; gap:10px; align-items:center; }
  .titleBtn { cursor: pointer; background: transparent; border: none; padding: 0; text-align:left; font: inherit; color: var(--text); }
  .titleBtn:hover { text-decoration: underline; }
  .pill { font-size: 12px; border: 1px solid var(--border); border-radius: 999px; padding: 2px 8px; color: var(--muted); }
  .editor { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--border); display:flex; gap: 14px; flex-wrap: wrap; }

  .iconBtn { background: transparent; border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 10px; font-weight: 800; display:inline-flex; align-items:center; justify-content:center; }
  /* dots (removed) */

  .trash { background: transparent; border: 1px solid rgba(255, 107, 107, 0.55); color: var(--danger); }
  .trash:hover { filter: brightness(1.08); }
  .field { display:flex; flex-direction:column; gap: 6px; }
  .shareBox { display:flex; flex-direction:column; gap:6px; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: rgba(255,255,255,0.02); }
  .shareRow { display:flex; gap:8px; align-items:center; font-size: 13px; color: var(--text); }
  .field label { font-size: 12px; color: var(--muted); }
  .label { font-size: 12px; color: var(--muted); }
  select { padding: 10px; border-radius: 10px; min-width: 180px; }
  .done { text-decoration: line-through; color: var(--muted); }
  /* (todo description removed) */
  .meta { margin-left: 28px; margin-top: 6px; color: var(--muted); font-size: 12px; }

  .toast { position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%); background: var(--panel); border: 1px solid var(--border); border-radius: 999px; padding: 10px 12px; display:flex; gap: 10px; align-items:center; z-index: 60; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
  .toastMsg { color: var(--text); font-size: 13px; }
  .toastBtn { background: transparent; border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 999px; font-weight: 900; }
</style>
