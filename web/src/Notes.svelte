<script lang="ts">
  import type { User } from './api';
  import { listUsers } from './api';
  import { getNote, patchNote, deleteNote, createNote, listNotes, listNoteGroups, createNoteGroup } from './notes_api';

  export let initialSelectedId: string | null = null;

  export type NoteGroup = { id: string; name: string };
  export type Note = { id: string; group_id?: string | null; title: string; body_md: string; shared_with: string[]; version: number; updated_at: number };

  let users: User[] = [];
  let groups: NoteGroup[] = [];
  let activeGroupId: string | null = null;
  let notes: Note[] = [];

  let q = '';

  let selectedId: string | null = null;
  let title = '';
  let body = '';
  let sharedWith: string[] = [];
  let version: number | null = null;

  let newGroupName = '';
  let newTitle = '';
  let err: string | null = null;
  let loading = true;

  let saveStatus: 'idle' | 'dirty' | 'saving' | 'saved' | 'error' = 'idle';
  let saveMsg = '';
  let saveTimer: any = null;
  let lastSavedAt: number | null = null;

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
      notes = await listNotes(activeGroupId, q);
      // If the currently-selected note no longer exists in this view, clear the editor.
      if (selectedId && !notes.some(n => n.id === selectedId)) {
        selectedId = null;
        title = '';
        body = '';
        sharedWith = [];
        version = null;
      }

      // Deep-link support: /app/notes/:id
      if (initialSelectedId && !selectedId) {
        let found = notes.find(n => n.id === initialSelectedId);
        if (!found) {
          // Fetch directly; then switch group and reload that group's notes.
          const n = await getNote(initialSelectedId);
          if (n.group_id && n.group_id !== activeGroupId) {
            activeGroupId = n.group_id;
            notes = await listNotes(activeGroupId, q);
          }
          found = notes.find(x => x.id === initialSelectedId) || n;
        }
        if (found) pick(found);
      }
    } catch (e:any) {
      err = e?.message || String(e);
    } finally {
      loading = false;
    }
  }

  function onGroupChange() {
    // Switching groups should not keep an unrelated note open.
    selectedId = null;
    title = '';
    body = '';
    sharedWith = [];
    version = null;
    refresh();
  }

  function closeEditor() {
    selectedId = null;
    title = '';
    body = '';
    sharedWith = [];
    version = null;
    saveStatus = 'idle';
    saveMsg = '';
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }

    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    history.pushState({}, '', `${base}notes`);
  }

  async function copyLink(id: string) {
    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    const url = `${location.origin}${base}notes/${encodeURIComponent(id)}`;
    try { await navigator.clipboard.writeText(url); }
    catch (e:any) { err = e?.message || String(e); }
  }

  function pick(n: Note) {
    selectedId = n.id;
    title = n.title;
    body = n.body_md || '';
    sharedWith = n.shared_with || [];
    version = n.version;

    saveStatus = 'idle';
    saveMsg = '';

    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    history.pushState({}, '', `${base}notes/${encodeURIComponent(n.id)}`);
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

  function markDirty() {
    if (!selectedId) return;
    if (saveStatus !== 'saving') saveStatus = 'dirty';
    saveMsg = '';

    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveTimer = null;
      void save();
    }, 650);
  }

  async function save() {
    if (!selectedId || version === null) return;
    // If nothing changed recently, don't spam saves.
    if (saveStatus === 'idle' || saveStatus === 'saved') return;

    saveStatus = 'saving';
    saveMsg = '';
    err = null;

    try {
      const n = await patchNote(selectedId, { title, body_md: body, shared_with: sharedWith, if_version: version });
      version = n.version;
      notes = notes.map(x => x.id === n.id ? n : x);
      saveStatus = 'saved';
      lastSavedAt = Date.now();
    } catch (e:any) {
      const msg = e?.message || String(e);
      // If we hit a version conflict, refresh and let user continue.
      err = msg;
      saveStatus = 'error';
      saveMsg = msg;
      await refresh();
    }
  }

  refresh();
</script>

<div class="grid" class:editing={!!selectedId}>
  <div class="sidebar">
    <div class="row">
      <h3>Notes</h3>
      <select bind:value={activeGroupId} on:change={onGroupChange}>
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

    <div class="searchRow">
      <input bind:value={q} placeholder="Search…" on:input={refresh} />
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
        <button class="back" type="button" on:click={closeEditor}>Back</button>
        <input class="title" bind:value={title} placeholder="Title" on:input={markDirty} />
        <div class="status">
          {#if saveStatus === 'saving'}Saving…{/if}
          {#if saveStatus === 'dirty'}Unsaved{/if}
          {#if saveStatus === 'saved'}Saved{/if}
          {#if saveStatus === 'error'}Save error{/if}
        </div>
        <button class="iconBtn" type="button" title="Copy link" aria-label="Copy link" on:click={() => selectedId && copyLink(selectedId)}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3ZM5 5h6v2H7v10h10v-4h2v6H5V5Z" />
          </svg>
        </button>

        <button on:click={save} disabled={!selectedId || version===null || saveStatus==='saving'}>Save</button>

        <button class="trash" type="button" on:click={async () => {
          if (!selectedId) return;
          if (!confirm('Delete this note?')) return;
          try {
            await deleteNote(selectedId);
            await refresh();
            closeEditor();
          } catch (e:any) {
            err = e?.message || String(e);
          }
        }}>Delete</button>
      </div>

      <textarea class="body" bind:value={body} on:input={markDirty} placeholder="# Markdown note\n\nWrite here…"></textarea>

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
                markDirty();
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
  @media (max-width: 900px){
    .grid { grid-template-columns: 1fr; }
    /* Mobile-first: list view OR editor view (full-screen) */
    .grid.editing .sidebar { display:none; }
    .grid.editing .editor { padding: 0; border: none; background: transparent; overflow-x: hidden; }

    /* Make the header fit small screens (avoid horizontal overflow) */
    .grid.editing .head {
      position: sticky;
      top: 0;
      background: var(--bg);
      padding: 10px 0;
      z-index: 2;
      flex-wrap: wrap;
      gap: 8px;
    }

    .grid.editing .back { display:inline-flex; }

    .grid.editing .head .title {
      flex: 1 1 100%;
      min-width: 0;
      order: 2;
    }

    .grid.editing .status { display:none; }

    .grid.editing .head button {
      padding: 8px 10px;
    }

    .body { max-width: 100%; box-sizing: border-box; }
  }

  .sidebar { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
  .row { display:flex; justify-content:space-between; align-items:center; gap:10px; }
  h3 { margin: 0; }
  select, input, textarea { padding: 10px; border-radius: 10px; box-sizing: border-box; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); font-weight: 800; }

  .addRow { display:flex; gap:8px; margin-top: 10px; }
  .addRow input { flex: 1; }

  .searchRow { margin-top: 10px; }
  .searchRow input { width: 100%; }

  .list { list-style:none; padding:0; margin: 12px 0 0; display:flex; flex-direction:column; gap:8px; }
  .list button { width:100%; text-align:left; background: transparent; color: var(--text); border: 1px solid var(--border); }
  .list button.selected { outline: 2px solid rgba(255,255,255,0.18); }

  .editor { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
  .head { display:flex; gap:10px; align-items:center; }
  .head .title { flex: 1; font-weight: 800; min-width: 0; }
  .status { font-size: 12px; color: var(--muted); min-width: 70px; text-align: right; }
  .back { display:none; background: transparent; border: 1px solid var(--border); color: var(--text); }

  .iconBtn { background: transparent; border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 10px; font-weight: 800; }
  /* dots (removed) */

  .trash { background: transparent; border: 1px solid rgba(255, 107, 107, 0.55); color: var(--danger); }
  .trash:hover { filter: brightness(1.08); }
  .body { width: 100%; min-height: 320px; margin-top: 10px; resize: vertical; }

  .share { margin-top: 10px; }
  .label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .shareBox { display:flex; flex-direction:column; gap:6px; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: rgba(255,255,255,0.02); }
  .shareRow { display:flex; gap:8px; align-items:center; font-size: 13px; color: var(--text); }

  .err { margin-top: 10px; color: var(--danger); font-size: 13px; }
  .hint { margin-top: 8px; color: var(--muted); font-size: 12px; }
  .empty { color: var(--muted); padding: 20px; }
</style>
