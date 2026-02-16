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
    <label>Username</label>
    <input bind:value={handle} placeholder="jon" autocapitalize="none" />
  </div>
  <div class="row">
    <label>Password</label>
    <input bind:value={password} type="password" />
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
  .card { border: 1px solid #ddd; border-radius: 12px; padding: 14px; }
  .row { display:flex; flex-direction:column; gap:6px; margin: 10px 0; }
  label { font-size: 12px; color: #555; }
  input { padding: 10px; border-radius: 10px; border: 1px solid #ccc; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid #111; background: #111; color: #fff; width: 100%; }
  button:disabled { opacity: 0.5; }
  .err { margin: 10px 0; color: #b00020; font-size: 13px; }
  .hint { margin: 10px 0 0; color: #666; font-size: 12px; }
</style>
