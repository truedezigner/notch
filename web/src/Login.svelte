<script lang="ts">
  import { login, setToken } from './api';

  export let onDone: () => void;

  let handle = '';
  let password = '';
  let err: string | null = null;
  let loading = false;

  async function submit() {
    err = null;
    loading = true;
    try {
      const r = await login(handle.trim(), password);
      setToken(r.token);
      onDone();
    } catch (e: any) {
      err = e?.message || String(e);
    } finally {
      loading = false;
    }
  }
</script>

<div class="card">
  <h3>Login</h3>
  <div class="row">
    <label for="handle">Username</label>
    <input id="handle" bind:value={handle} placeholder="jon" autocapitalize="none" />
  </div>
  <div class="row">
    <label for="pw">Password</label>
    <input id="pw" bind:value={password} type="password" />
  </div>

  {#if err}
    <div class="err">{err}</div>
  {/if}

  <button on:click={submit} disabled={loading || !handle || !password}>
    {loading ? 'Signing in…' : 'Sign in'}
  </button>

  <p class="hint">Notch is LAN-first; use the same URL on phone + desktop.</p>
</div>

<style>
  .card { border: 1px solid var(--border); border-radius: 12px; padding: 14px; background: var(--panel); }
  .row { display:flex; flex-direction:column; gap:6px; margin: 10px 0; }
  label { font-size: 12px; color: var(--muted); }
  input { padding: 10px; border-radius: 10px; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); width: 100%; font-weight: 700; }
  button:disabled { opacity: 0.5; }
  .err { margin: 10px 0; color: var(--danger); font-size: 13px; }
  .hint { margin: 10px 0 0; color: var(--muted); font-size: 12px; }
</style>
