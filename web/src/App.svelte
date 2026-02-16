<script lang="ts">
  import Login from './Login.svelte';
  import Todos from './Todos.svelte';
  import Notes from './Notes.svelte';
  import { getToken } from './api';

  let authed = !!getToken();
  let route = '';
  let tab: 'todos' | 'notes' = 'todos';
  let todoId: string | null = null;
  let noteId: string | null = null;

  function parseRoute() {
    const p = location.pathname;
    const idx = p.indexOf('/app/');
    const sub = idx >= 0 ? p.slice(idx + 5) : '';
    route = sub || '';

    // tabs
    if (route.startsWith('notes')) tab = 'notes';
    else tab = 'todos';

    const m = route.match(/^todos\/([^/]+)/);
    todoId = m ? decodeURIComponent(m[1]) : null;

    const n = route.match(/^notes\/([^/]+)/);
    noteId = n ? decodeURIComponent(n[1]) : null;
  }

  function goto(next: 'todos' | 'notes') {
    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    history.pushState({}, '', next === 'notes' ? `${base}notes` : `${base}`);
    parseRoute();
  }

  parseRoute();
  window.addEventListener('popstate', parseRoute);

  function done(){ authed = true; parseRoute(); }
</script>

<main style="max-width: 820px; margin: 16px auto; font-family: system-ui, -apple-system, sans-serif; padding: 0 12px;">
  <h2>Notch</h2>
  {#if authed}
    <div class="tabs">
      <button class:active={tab==='todos'} on:click={() => goto('todos')}>Todos</button>
      <button class:active={tab==='notes'} on:click={() => goto('notes')}>Notes</button>
    </div>

    {#if tab === 'todos'}
      <Todos initialExpandedId={todoId} />
    {:else}
      <Notes initialSelectedId={noteId} />
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
