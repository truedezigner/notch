<script lang="ts">
  import Login from './Login.svelte';
  import Todos from './Todos.svelte';
  import { getToken } from './api';

  let authed = !!getToken();
  function done(){ authed = true; }
</script>

<main style="max-width: 820px; margin: 16px auto; font-family: system-ui, -apple-system, sans-serif; padding: 0 12px;">
  <h2>Notch</h2>
  {#if authed}
    <Todos />
  {:else}
    <Login onDone={done} />
  {/if}
</main>
