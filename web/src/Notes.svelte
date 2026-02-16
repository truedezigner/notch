<script lang="ts">
  import type { User } from './api';
  import { listUsers, patchNote, createNote, listNotes, listNoteGroups, createNoteGroup } from './notes_api';

  export type NoteGroup = { id: string; name: string };
  export type Note = { id: string; group_id?: string | null; title: string; body_md: string; shared_with: string[]; version: number; updated_at: number };

  let users: User[] = [];
  let groups: NoteGroup[] = [];
  let activeGroupId: string | null = null;
  let notes: Note[] = [];

  let selectedId: string | null = null;
  let title = '';
  let body = '';
  let sharedWith: string[] = [];
  let version: number | null = null;

  let newGroupName = '';
  let newTitle = '';
  let err: string | null = null;
  let loading = true;

  function userLabel(id: string) {
    const u = users.find(u => u.id === id);
    return u ? u.display_name : id;
  }

  async function refresh() {
    loading = true;
    err = null;
    try {
      users = await listUsers();
      groups = await listNoteGroups();
      if (!activeGroupId && groups.length) activeGroupId = groups[0].id;
      notes = await listNotes(activeGroupId);
    } catch (e:any) {
      err = e?.message || String(e);
    } finally {
      loading = false;
    }
  }

  function pick(n: Note) {
    selectedId = n.id;
    title = n.title;
    body = n.body_md || '';
    sharedWith = n.shared_with || [];
    version = n.version;
  }

  async function addGroup() {
    const name = newGroupName.trim();
    if (!name) return;
    try {
      const g = await createNoteGroup(name);
      groups = [...groups, g].sort((a,b)=>a.name.localeCompare(b.name));
      activeGroupId = g.id;
      newGroupName = '';
      await refresh();
    } catch (e:any) { err = e?.message || String(e); }
  }

  async function addNote() {
    const t = newTitle.trim();
    if (!t) return;
    try {
      const n = await createNote(t, activeGroupId);
      notes = [n, ...notes];
      newTitle = '';
      pick(n);
    } catch (e:any) { err = e?.message || String(e); }
  }

  async function save() {
    if (!selectedId || version === null) return;
    try {
      const n = await patchNote(selectedId, { title, body_md: body, shared_with: sharedWith, if_version: version });
      version = n.version;
      notes = notes.map(x => x.id === n.id ? n : x);
    } catch (e:any) { err = e?.message || String(e); await refresh(); }
  }

  refresh();
</script>

<div class="grid">
  <div class="sidebar">
    <div class="row">
      <h3>Notes</h3>
      <select bind:value={activeGroupId} on:change={refresh}>
        {#each groups as g}
          <option value={g.id}>{g.name}</option>
        {/each}
      </select>
    </div>

    <div class="addRow">
      <input bind:value={newGroupName} placeholder="New group…" on:keydown={(e)=>e.key==='Enter'&&addGroup()} />
      <button on:click={addGroup} disabled={!newGroupName.trim()}>Add group</button>
    </div>

    <div class="addRow">
      <input bind:value={newTitle} placeholder="New note…" on:keydown={(e)=>e.key==='Enter'&&addNote()} />
      <button on:click={addNote} disabled={!newTitle.trim()}>Add</button>
    </div>

    {#if err}
      <div class="err">{err}</div>
    {/if}

    {#if loading}
      <div class="hint">Loading…</div>
    {:else}
      <ul class="list">
        {#each notes as n (n.id)}
          <li>
            <button type="button" class:selected={selectedId===n.id} on:click={() => pick(n)}>
              {n.title}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="editor">
    {#if selectedId}
      <div class="head">
        <input class="title" bind:value={title} placeholder="Title" />
        <button on:click={save}>Save</button>
      </div>

      <textarea class="body" bind:value={body} placeholder="# Markdown note\n\nWrite here…"></textarea>

      <div class="share">
        <div class="label">Shared with</div>
        <div class="shareBox">
          {#each users as u}
            <label class="shareRow">
              <input type="checkbox" checked={sharedWith.includes(u.id)} on:change={(e)=>{
                const checked = (e.currentTarget as HTMLInputElement).checked;
                const next = new Set(sharedWith);
                if (checked) next.add(u.id); else next.delete(u.id);
                sharedWith = Array.from(next);
              }} />
              <span>{u.display_name}</span>
            </label>
          {/each}
        </div>
        <div class="hint">(Share changes save when you click Save.)</div>
      </div>
    {:else}
      <div class="empty">Select a note or create one.</div>
    {/if}
  </div>
</div>

<style>
  .grid { display:grid; grid-template-columns: 280px 1fr; gap: 12px; }
  @media (max-width: 900px){ .grid { grid-template-columns: 1fr; } }

  .sidebar { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
  .row { display:flex; justify-content:space-between; align-items:center; gap:10px; }
  h3 { margin: 0; }
  select, input, textarea { padding: 10px; border-radius: 10px; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); font-weight: 800; }

  .addRow { display:flex; gap:8px; margin-top: 10px; }
  .addRow input { flex: 1; }

  .list { list-style:none; padding:0; margin: 12px 0 0; display:flex; flex-direction:column; gap:8px; }
  .list button { width:100%; text-align:left; background: transparent; color: var(--text); border: 1px solid var(--border); }
  .list button.selected { outline: 2px solid rgba(255,255,255,0.18); }

  .editor { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
  .head { display:flex; gap:10px; align-items:center; }
  .head .title { flex: 1; font-weight: 800; }
  .body { width: 100%; min-height: 320px; margin-top: 10px; resize: vertical; }

  .share { margin-top: 10px; }
  .label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .shareBox { display:flex; flex-direction:column; gap:6px; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: rgba(255,255,255,0.02); }
  .shareRow { display:flex; gap:8px; align-items:center; font-size: 13px; color: var(--text); }

  .err { margin-top: 10px; color: var(--danger); font-size: 13px; }
  .hint { margin-top: 8px; color: var(--muted); font-size: 12px; }
  .empty { color: var(--muted); padding: 20px; }
</style>
