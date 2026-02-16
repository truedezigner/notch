<script lang="ts">
  import type { User } from './api';
  import { adminCreateUser, listUsers } from './api';

  export let me: User;

  let handle = '';
  let displayName = '';
  let password = '';

  let users: User[] = [];
  let err: string | null = null;
  let ok: string | null = null;
  let loading = false;

  async function refresh() {
    try {
      users = await listUsers();
    } catch (e:any) {
      err = e?.message || String(e);
    }
  }

  async function submit() {
    err = null;
    ok = null;
    loading = true;
    try {
      const u = await adminCreateUser(handle.trim().toLowerCase(), password, displayName.trim() || undefined);
      ok = `Created user: ${u.handle}`;
      handle = '';
      displayName = '';
      password = '';
      await refresh();
    } catch (e:any) {
      err = e?.message || String(e);
    } finally {
      loading = false;
    }
  }

  refresh();
</script>

{#if !me?.is_admin}
  <div class="card">Admin only.</div>
{:else}
  <div class="card">
    <h3>Admin</h3>
    <div class="hint">Create users (LAN MVP). Admin = first user ever created.</div>

    <div class="row">
      <label for="h">Handle</label>
      <input id="h" bind:value={handle} placeholder="elizabeth" autocapitalize="none" />
    </div>

    <div class="row">
      <label for="dn">Display name</label>
      <input id="dn" bind:value={displayName} placeholder="Elizabeth" />
    </div>

    <div class="row">
      <label for="p">Password</label>
      <input id="p" bind:value={password} type="password" />
    </div>

    {#if err}
      <div class="err">{err}</div>
    {/if}
    {#if ok}
      <div class="ok">{ok}</div>
    {/if}

    <button on:click={submit} disabled={loading || !handle.trim() || !password}>Create user</button>

    <div class="divider"></div>

    <div class="subhead">Users</div>
    <ul class="u">
      {#each users as u}
        <li>
          <span class="name">{u.display_name}</span>
          <span class="muted">@{u.handle}</span>
          {#if u.is_admin}<span class="pill">admin</span>{/if}
        </li>
      {/each}
    </ul>
  </div>
{/if}

<style>
  .card { border: 1px solid var(--border); border-radius: 12px; padding: 14px; background: var(--panel); }
  .row { display:flex; flex-direction:column; gap:6px; margin: 10px 0; }
  label { font-size: 12px; color: var(--muted); }
  input { padding: 10px; border-radius: 10px; box-sizing: border-box; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); width: 100%; font-weight: 800; }
  button:disabled { opacity: 0.5; }
  .err { margin-top: 10px; color: var(--danger); font-size: 13px; }
  .ok { margin-top: 10px; color: var(--text); font-size: 13px; }
  .hint { margin-top: 6px; color: var(--muted); font-size: 12px; }
  .divider { height: 1px; background: var(--border); opacity: 0.7; margin: 14px 0; }
  .subhead { font-weight: 800; margin-bottom: 8px; }
  .u { list-style: none; padding: 0; margin: 0; display:flex; flex-direction:column; gap: 8px; }
  .u li { display:flex; gap: 8px; align-items:center; flex-wrap: wrap; }
  .name { font-weight: 800; }
  .muted { color: var(--muted); }
  .pill { font-size: 12px; border: 1px solid var(--border); border-radius: 999px; padding: 2px 8px; color: var(--muted); }
</style>
