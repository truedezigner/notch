<script lang="ts">
  import Login from './Login.svelte';
  import Todos from './Todos.svelte';
  import { getToken } from './api';

  let authed = !!getToken();
  let route = '';
  let todoId: string | null = null;

  function parseRoute() {
    // /app/..., but in dev vite serves at / so keep it flexible.
    const p = location.pathname;
    const idx = p.indexOf('/app/');
    const sub = idx >= 0 ? p.slice(idx + 5) : '';
    route = sub || '';
    const m = route.match(/^todos\/([^/]+)/);
    todoId = m ? decodeURIComponent(m[1]) : null;
  }

  parseRoute();
  window.addEventListener('popstate', parseRoute);

  function done(){ authed = true; parseRoute(); }
</script>

<main style="max-width: 820px; margin: 16px auto; font-family: system-ui, -apple-system, sans-serif; padding: 0 12px;">
  <h2>Notch</h2>
  {#if authed}
    <Todos initialExpandedId={todoId} />
  {:else}
    <Login onDone={done} />
  {/if}
</main>
