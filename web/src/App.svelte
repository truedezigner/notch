<script lang="ts">
  import Login from './Login.svelte';
  import Todos from './Todos.svelte';
  import Notes from './Notes.svelte';
  import Admin from './Admin.svelte';
  import type { User } from './api';
  import { getToken, me } from './api';

  let authed = !!getToken();
  let currentUser: User | null = null;
  let route = '';
  let tab: 'todos' | 'notes' | 'admin' = 'todos';
  let todoId: string | null = null;
  let noteId: string | null = null;

  function parseRoute() {
    const p = location.pathname;
    const idx = p.indexOf('/app/');
    const sub = idx >= 0 ? p.slice(idx + 5) : '';
    route = sub || '';

    // tabs
    if (route.startsWith('admin')) tab = 'admin';
    else if (route.startsWith('notes')) tab = 'notes';
    else tab = 'todos';

    const m = route.match(/^todos\/([^/]+)/);
    todoId = m ? decodeURIComponent(m[1]) : null;

    const n = route.match(/^notes\/([^/]+)/);
    noteId = n ? decodeURIComponent(n[1]) : null;
  }

  function goto(next: 'todos' | 'notes' | 'admin') {
    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    if (next === 'notes') history.pushState({}, '', `${base}notes`);
    else if (next === 'admin') history.pushState({}, '', `${base}admin`);
    else history.pushState({}, '', `${base}`);
    parseRoute();
  }

  parseRoute();
  window.addEventListener('popstate', parseRoute);

  async function loadMe() {
    if (!authed) { currentUser = null; return; }
    try { currentUser = await me(); }
    catch { currentUser = null; }
  }

  function done(){ authed = true; parseRoute(); void loadMe(); }

  loadMe();
</script>

<main style="max-width: 820px; margin: 16px auto; font-family: system-ui, -apple-system, sans-serif; padding: 0 12px;">
  <h2>Notch</h2>
  {#if authed}
    <div class="tabs">
      <button class:active={tab==='todos'} on:click={() => goto('todos')}>Todos</button>
      <button class:active={tab==='notes'} on:click={() => goto('notes')}>Notes</button>
      {#if currentUser?.is_admin}
        <button class:active={tab==='admin'} on:click={() => goto('admin')}>Admin</button>
      {/if}
    </div>

    {#if tab === 'todos'}
      <Todos initialExpandedId={todoId} />
    {:else if tab === 'notes'}
      <Notes initialSelectedId={noteId} />
    {:else}
      {#if currentUser}
        <Admin me={currentUser} />
      {/if}
    {/if}
  {:else}
    <Login onDone={done} />
  {/if}

  <style>
    .tabs { display:flex; gap:8px; margin: 10px 0 14px; }
    .tabs button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--panel); color: var(--text); font-weight: 800; }
    .tabs button.active { border-color: rgba(255,255,255,0.35); }
  </style>
</main>
