<script lang="ts">
  import { tick } from 'svelte';
  import type { User } from './api';
  import { listUsers } from './api';
  import { getNote, patchNote, deleteNote, createNote, listNotes, listNoteGroups, createNoteGroup, patchNoteGroup, createNoteShare } from './notes_api';

  export let initialSelectedId: string | null = null;
  let handledInitial = false;

  export type NoteGroup = { id: string; name: string; shared_with?: string[] };
  export type Note = { id: string; group_id?: string | null; title: string; body_md: string; shared_with: string[]; version: number; updated_at: number };

  let users: User[] = [];
  let groups: NoteGroup[] = [];
  // '' means "All groups"
  let activeGroupId: string = '';
  let notes: Note[] = [];

  let groupSharedWith: string[] = [];

  function groupLabel(id?: string | null) {
    if (!id) return '';
    const g = groups.find(x => x.id === id);
    return g ? g.name : '';
  }
  let q = '';

  let selectedId: string | null = null;
  let title = '';
  let body = '';
  let sharedWith: string[] = [];
  let version: number | null = null;

  let titleEl: HTMLInputElement | null = null;
  let bodyEl: HTMLTextAreaElement | null = null;
  let newNoteEl: HTMLInputElement | null = null;
  let newGroupEl: HTMLInputElement | null = null;

  let newGroupName = '';
  let newTitle = '';
  let err: string | null = null;
  let loading = true;

  let showSearch = false;
  let showNewNote = false;
  let showNewGroup = false;
  let showGroupShare = false;

  let saveStatus: 'idle' | 'dirty' | 'saving' | 'saved' | 'error' = 'idle';
  let viewMode: 'edit' | 'preview' = 'edit';
  let saveMsg = '';
  let saveTimer: any = null;
  let lastSavedAt: number | null = null;

  function userLabel(id: string) {
    const u = users.find(u => u.id === id);
    return u ? u.display_name : id;
  }

  function snippet(md: string) {
    const s = String(md || '').replace(/\s+/g, ' ').trim();
    if (!s) return '—';
    return s.length > 44 ? s.slice(0, 44) + '…' : s;
  }

  function escapeHtml(s: string) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function mdToHtml(md: string) {
    // Minimal, safe-ish markdown rendering (no raw HTML).
    const src = String(md || '').replace(/\r\n/g, '\n');
    const lines = src.split('\n');

    const out: string[] = [];
    let inCode = false;
    let codeBuf: string[] = [];

    function flushCode() {
      if (!codeBuf.length) return;
      out.push(`<pre><code>${escapeHtml(codeBuf.join('\n'))}</code></pre>`);
      codeBuf = [];
    }

    for (const raw of lines) {
      const line = raw;
      if (line.startsWith('```')) {
        if (inCode) {
          inCode = false;
          flushCode();
        } else {
          inCode = true;
        }
        continue;
      }
      if (inCode) {
        codeBuf.push(line);
        continue;
      }

      const t = line.trim();
      if (!t) { out.push(''); continue; }

      // headings
      const m = t.match(/^(#{1,6})\s+(.*)$/);
      if (m) {
        const lvl = m[1].length;
        out.push(`<h${lvl}>${inlineMd(m[2])}</h${lvl}>`);
        continue;
      }

      // unordered list
      const lm = t.match(/^[-*]\s+(.*)$/);
      if (lm) {
        out.push(`<li>${inlineMd(lm[1])}</li>`);
        continue;
      }

      out.push(`<p>${inlineMd(t)}</p>`);
    }

    if (inCode) {
      inCode = false;
      flushCode();
    }

    // wrap consecutive <li> into <ul>
    const wrapped: string[] = [];
    let inUl = false;
    for (const chunk of out) {
      if (chunk.startsWith('<li>')) {
        if (!inUl) { wrapped.push('<ul>'); inUl = true; }
        wrapped.push(chunk);
      } else {
        if (inUl) { wrapped.push('</ul>'); inUl = false; }
        wrapped.push(chunk);
      }
    }
    if (inUl) wrapped.push('</ul>');

    return wrapped.filter(x => x !== '').join('\n');

    function inlineMd(s: string) {
      let v = escapeHtml(s);
      // code
      v = v.replace(/`([^`]+)`/g, (_m, a) => `<code>${escapeHtml(a)}</code>`);
      // bold
      v = v.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      // italics
      v = v.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      // links [text](url)
      v = v.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
      return v;
    }
  }

  function fmtRel(ts: number) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const diff = Date.now() - d.getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'now';
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`;
    const days = Math.floor(h / 24);
    if (days < 14) return `${days}d`;
    return d.toLocaleDateString();
  }

  async function refresh() {
    loading = true;
    err = null;
    try {
      users = await listUsers();
      groups = await listNoteGroups();
      // Default to All groups so individually-shared notes show up even if their group isn't shared.
      groupSharedWith = (groups.find(g => g.id === activeGroupId)?.shared_with as any) || [];
      notes = await listNotes(activeGroupId || null, q);
      // If the currently-selected note no longer exists in this view, clear the editor.
      if (selectedId && !notes.some(n => n.id === selectedId)) {
        selectedId = null;
        title = '';
        body = '';
        sharedWith = [];
        version = null;
      }

      // Deep-link support: /app/notes/:id (only once on initial load)
      if (!handledInitial && initialSelectedId && !selectedId) {
        handledInitial = true;
        let found = notes.find(n => n.id === initialSelectedId);
        if (!found) {
          // Fetch directly; then switch group and reload that group's notes.
          const n = await getNote(initialSelectedId);
          if (n.group_id && n.group_id !== activeGroupId) {
            activeGroupId = n.group_id;
            notes = await listNotes(activeGroupId || null, q);
          }
          found = notes.find(x => x.id === initialSelectedId) || n;
        }
        if (found) await pick(found);
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
    groupSharedWith = (groups.find(g => g.id === activeGroupId)?.shared_with as any) || [];
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

  async function copyText(t: string) {
    try {
      // navigator.clipboard can be undefined on some browsers/contexts.
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(t);
        return true;
      }
    } catch {
      // fall through
    }

    // Fallback: execCommand copy.
    try {
      const ta = document.createElement('textarea');
      ta.value = t;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (ok) return true;
    } catch {
      // fall through
    }

    // Last resort: prompt so user can copy manually.
    prompt('Copy this:', t);
    return false;
  }

  async function copyLink(id: string) {
    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    const url = `${location.origin}${base}notes/${encodeURIComponent(id)}`;
    try { await copyText(url); }
    catch (e:any) { err = e?.message || String(e); }
  }

  let shareDlgOpen = false;
  let shareNoteId: string | null = null;
  let shareNeverExpires = true;
  let shareHours = '24';
  let shareUrl: string | null = null;

  function openShareDlg(id: string) {
    shareNoteId = id;
    shareDlgOpen = true;
    shareUrl = null;
    shareNeverExpires = true;
    shareHours = '24';
  }

  async function createPublicShare() {
    if (!shareNoteId) return;
    err = null;

    let expires_in_seconds: number | null | undefined = undefined;
    if (shareNeverExpires) {
      expires_in_seconds = null;
    } else {
      const hours = Number(String(shareHours || '').trim());
      if (!Number.isFinite(hours) || hours <= 0) {
        err = 'Expiry must be a positive number of hours.';
        return;
      }
      expires_in_seconds = Math.floor(hours * 3600);
    }

    try {
      const r = await createNoteShare(shareNoteId, { can_edit: true, expires_in_seconds });
      shareUrl = `${location.origin}${r.url}`;
      await copyText(shareUrl);
      // Nice UX: open it too, so you can confirm it doesn't require login.
      window.open(shareUrl, '_blank', 'noopener');
    } catch (e:any) {
      err = e?.message || String(e);
    }
  }

  async function pick(n: Note) {
    selectedId = n.id;
    title = n.title;
    body = n.body_md || '';
    sharedWith = n.shared_with || [];
    version = n.version;

    saveStatus = 'idle';
    saveMsg = '';

    const base = location.pathname.includes('/app/') ? '/app/' : '/';
    history.pushState({}, '', `${base}notes/${encodeURIComponent(n.id)}`);

    await tick();
    // On mobile, jump into writing.
    (bodyEl || titleEl)?.focus();
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
      const n = await createNote(t, activeGroupId || null);
      notes = [n, ...notes];
      newTitle = '';
      await pick(n);
    } catch (e:any) { err = e?.message || String(e); }
  }

  function insertIntoBody(text: string, surround?: { before: string; after: string }) {
    if (!bodyEl) {
      body = body + text;
      markDirty();
      return;
    }
    const start = bodyEl.selectionStart ?? body.length;
    const end = bodyEl.selectionEnd ?? body.length;
    const sel = body.slice(start, end);

    let insert = text;
    if (surround) insert = surround.before + sel + surround.after;

    body = body.slice(0, start) + insert + body.slice(end);
    markDirty();

    tick().then(() => {
      if (!bodyEl) return;
      const pos = surround ? (start + surround.before.length + sel.length) : (start + insert.length);
      bodyEl.focus();
      bodyEl.setSelectionRange(pos, pos);
    });
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
        <option value="">All</option>
        {#each groups as g}
          <option value={g.id}>{g.name}</option>
        {/each}
      </select>
    </div>

    <!-- Mobile toolbar (keeps the list near the top) -->
    <div class="mobileBar">
      <button class="iconBtn" type="button" title="Search" aria-label="Search" on:click={() => { showSearch = !showSearch; }}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
          <path fill="currentColor" d="M10 4a6 6 0 1 1 0 12 6 6 0 0 1 0-12Zm0-2a8 8 0 1 0 4.9 14.3l4.4 4.4 1.4-1.4-4.4-4.4A8 8 0 0 0 10 2Z"/>
        </svg>
      </button>

      <button class="iconBtn" type="button" title="New note" aria-label="New note" on:click={async () => {
        showNewNote = !showNewNote;
        showNewGroup = false;
        await tick();
        newNoteEl?.focus();
      }}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
          <path fill="currentColor" d="M11 5h2v14h-2V5Zm-6 6h14v2H5v-2Z"/>
        </svg>
      </button>

      <button class="iconBtn" type="button" title="New group" aria-label="New group" on:click={async () => {
        showNewGroup = !showNewGroup;
        showNewNote = false;
        await tick();
        newGroupEl?.focus();
      }}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
          <path fill="currentColor" d="M10 6h11v2H10V6ZM3 6h5v5H3V6Zm7 10h11v2H10v-2ZM3 16h5v5H3v-5Z"/>
        </svg>
      </button>

      <button class="iconBtn" type="button" title="Group sharing" aria-label="Group sharing" on:click={() => { showGroupShare = !showGroupShare; }}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
          <path fill="currentColor" d="M16 11c1.66 0 3-1.34 3-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3ZM8 11c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3Zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13Zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h7v-2.5C24 14.17 18.33 13 16 13Z"/>
        </svg>
      </button>
    </div>

    <div class="controls">
      {#if showNewGroup}
        <div class="addRow">
          <input bind:this={newGroupEl} bind:value={newGroupName} placeholder="New group…" on:keydown={(e)=>e.key==='Enter'&&addGroup()} />
          <button on:click={addGroup} disabled={!newGroupName.trim()}>Add group</button>
        </div>
      {/if}

      {#if showNewNote}
        <div class="addRow">
          <input bind:this={newNoteEl} bind:value={newTitle} placeholder="New note…" on:keydown={(e)=>e.key==='Enter'&&addNote()} />
          <button on:click={addNote} disabled={!newTitle.trim()}>Add</button>
        </div>
      {/if}

      {#if showSearch}
        <div class="searchRow">
          <input bind:value={q} placeholder="Search…" on:input={refresh} />
        </div>
      {/if}

      {#if showGroupShare}
        <div class="share" style="margin-top: 10px;">
          <div class="label">Group shared with</div>
          <div class="shareBox">
            {#each users as u}
              <label class="shareRow">
                <input type="checkbox" checked={groupSharedWith.includes(u.id)} on:change={async (e)=>{
                  if (!activeGroupId) return;
                  const checked = (e.currentTarget as HTMLInputElement).checked;
                  const next = new Set(groupSharedWith);
                  if (checked) next.add(u.id); else next.delete(u.id);
                  groupSharedWith = Array.from(next);
                  try {
                    await patchNoteGroup(activeGroupId, { shared_with: groupSharedWith });
                    await refresh();
                  } catch (e2:any) { err = e2?.message || String(e2); }
                }} />
                <span>{u.display_name}</span>
              </label>
            {/each}
          </div>
          <div class="hint">(Sharing a group shares all notes in it.)</div>
        </div>
      {/if}
    </div>

    {#if err}
      <div class="err">{err}</div>
    {/if}

    {#if loading}
      <div class="hint">Loading…</div>
    {:else if !notes.length}
      <div class="hint">
        {#if q.trim()}
          No results.
        {:else}
          No notes yet.
        {/if}
      </div>
    {:else}
      <ul class="list">
        {#each notes as n (n.id)}
          <li>
            <button type="button" class:selected={selectedId===n.id} on:click={() => void pick(n)}>
              <div class="t">{n.title}</div>
              <div class="sub">
                <span class="snip">{snippet(n.body_md)}</span>
                {#if !activeGroupId && n.group_id}
                  <span class="dot">•</span>
                  <span class="pill2">{groupLabel(n.group_id)}</span>
                {/if}
                <span class="dot">•</span>
                <span class="ts">{fmtRel(n.updated_at)}</span>
              </div>
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
        <input class="title" bind:this={titleEl} bind:value={title} placeholder="Title" on:input={markDirty} />
        <div class="status">
          {#if saveStatus === 'saving'}Saving…{/if}
          {#if saveStatus === 'dirty'}Unsaved{/if}
          {#if saveStatus === 'saved'}Saved{/if}
          {#if saveStatus === 'error'}Save error{/if}
        </div>
        <button class="iconBtn" type="button" title="Create public editable link" aria-label="Create public editable link" on:click={() => selectedId && openShareDlg(selectedId)}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3ZM5 5h6v2H7v10h10v-4h2v6H5V5Z" />
          </svg>
        </button>

        <button class="iconBtn" type="button" title={viewMode==='edit' ? 'Preview' : 'Edit'} aria-label={viewMode==='edit' ? 'Preview' : 'Edit'} on:click={() => { viewMode = viewMode === 'edit' ? 'preview' : 'edit'; }}>
          {#if viewMode === 'edit'}
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
              <path fill="currentColor" d="M4 6h16v2H4V6Zm0 5h10v2H4v-2Zm0 5h16v2H4v-2Z" />
            </svg>
          {:else}
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
              <path fill="currentColor" d="M12 5c-7 0-10 7-10 7s3 7 10 7 10-7 10-7-3-7-10-7Zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10Z" />
            </svg>
          {/if}
        </button>

        <button class="trash" type="button" title="Delete" aria-label="Delete" on:click={async () => {
          if (!selectedId) return;
          if (!confirm('Move this note to trash?')) return;
          try {
            await deleteNote(selectedId);
            await refresh();
            closeEditor();
          } catch (e:any) {
            err = e?.message || String(e);
          }
        }}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
            <path fill="currentColor" d="M9 3h6l1 2h5v2H3V5h5l1-2Zm1 6h2v10h-2V9Zm4 0h2v10h-2V9ZM7 9h2v10H7V9Z" />
          </svg>
        </button>
      </div>

      <!-- Group picker moved below -->

      {#if viewMode === 'edit'}
        <div class="mdbar" aria-label="Markdown tools">
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '# ', after: '' })} title="Heading 1">#</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '## ', after: '' })} title="Heading 2">##</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '```\n', after: '\n```\n' })} title="Code block">```</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '`', after: '`' })} title="Inline code">`</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '**', after: '**' })} title="Bold">B</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '*', after: '*' })} title="Italic">I</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('', { before: '- ', after: '' })} title="Bullet">•</button>
          <button type="button" class="mdBtn" on:click={() => insertIntoBody('[text](https://example.com)')} title="Link">Link</button>
        </div>
        <textarea class="body" bind:this={bodyEl} bind:value={body} on:input={markDirty} placeholder="# Markdown note\n\nWrite here…"></textarea>
      {:else}
        <div class="preview" role="region" aria-label="Markdown preview">{@html mdToHtml(body)}</div>
      {/if}

      <div class="detailsRow">
        <div class="shareCol">
          <details class="noteShare" open={groupSharedWith.length === 0}>
            <summary class="noteShareSummary">
              {#if groupSharedWith.length}
                Note-specific sharing
              {:else}
                Shared with
              {/if}
            </summary>
            <div class="share" style="margin-top: 8px;">
              {#if groupSharedWith.length}
                <div class="hint">This note is already shared with the group. Use this only to share the note beyond the group.</div>
              {/if}
              <div class="shareBox shareScroll">
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
              <div class="hint">(Share changes autosave.)</div>
            </div>
          </details>
        </div>

        <div class="groupCol">
          <div class="field">
            <label for="note-group">Group</label>
            <select id="note-group" value={activeGroupId || ''} on:change={async (e)=>{
              const v = (e.currentTarget as HTMLSelectElement).value;
              if (!selectedId || version === null) return;
              try {
                const updated = await patchNote(selectedId, { group_id: v || null, if_version: version });
                version = updated.version;
                // stick to the note's new group
                activeGroupId = updated.group_id || '';
                await refresh();
              } catch (e2:any) { err = e2?.message || String(e2); await refresh(); }
            }}>
              {#each groups as g}
                <option value={g.id}>{g.name}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>
    {:else}
      <div class="empty">Select a note or create one.</div>
    {/if}
  </div>
</div>

{#if shareDlgOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="modalOverlay" role="presentation" on:click={() => { shareDlgOpen = false; }}>
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="modal" role="dialog" tabindex="-1" aria-modal="true" aria-label="Public link" on:click|stopPropagation>
      <div class="modalHead">
        <div class="modalTitle">Public link</div>
        <button class="iconBtn" type="button" aria-label="Close" title="Close" on:click={() => { shareDlgOpen = false; }}>✕</button>
      </div>

      <div class="hint">Anyone with the link can edit. Link autosaves.</div>

      <label class="row2">
        <input type="checkbox" bind:checked={shareNeverExpires} />
        <span>Never expires</span>
      </label>

      {#if !shareNeverExpires}
        <div class="row3">
          <label for="exp">Expires in (hours)</label>
          <input id="exp" inputmode="numeric" bind:value={shareHours} />
        </div>
      {/if}

      <div class="actions">
        <button on:click={createPublicShare}>Create link</button>
        <button class="btnGhost" on:click={() => { shareDlgOpen = false; }}>Cancel</button>
      </div>

      {#if shareUrl}
        <div class="row3" style="margin-top: 10px;">
          <label for="shareurl">Link</label>
          <input id="shareurl" value={shareUrl} readonly />
        </div>
        <div class="actions" style="margin-top: 10px;">
          <button class="btnGhost" on:click={() => shareUrl && copyText(shareUrl)}>Copy</button>
          <button class="btnGhost" on:click={() => shareUrl && window.open(shareUrl, '_blank', 'noopener')}>Open</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .grid { display:grid; grid-template-columns: 280px 1fr; gap: 12px; }
  @media (max-width: 900px){
    .grid { grid-template-columns: 1fr; }

    /* Show the compact toolbar on mobile; hide bulky controls by default */
    .mobileBar { display:flex; }

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

  /* Desktop: hide the mobile toolbar only when we have a fine pointer + hover (real desktop). */
  @media (min-width: 901px) and (hover: hover) and (pointer: fine) {
    .mobileBar { display:none; }
  }

  .sidebar { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
  .row { display:flex; justify-content:space-between; align-items:center; gap:10px; }
  h3 { margin: 0; }
  select, input, textarea { padding: 10px; border-radius: 10px; box-sizing: border-box; }
  button { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--btn); background: var(--btn); color: var(--btnText); font-weight: 800; }

  .mobileBar { display:flex; gap: 8px; margin-top: 10px; }

  .controls { margin-top: 0; }

  .addRow { display:flex; gap:8px; margin-top: 10px; }
  .addRow input { flex: 1; }

  .searchRow { margin-top: 10px; }
  .searchRow input { width: 100%; }

  .list { list-style:none; padding:0; margin: 12px 0 0; display:flex; flex-direction:column; gap:8px; }
  .list button { width:100%; text-align:left; background: transparent; color: var(--text); border: 1px solid var(--border); padding: 10px 10px; }
  .list button.selected { outline: 2px solid rgba(255,255,255,0.18); }
  .t { font-weight: 800; }
  .sub { margin-top: 4px; display:flex; gap:6px; align-items:center; color: var(--muted); font-size: 12px; flex-wrap: wrap; }
  .snip { flex: 1; min-width: 120px; overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot { opacity: 0.7; }
  .ts { white-space: nowrap; }
  .pill2 { font-size: 12px; border: 1px solid var(--border); border-radius: 999px; padding: 1px 7px; color: var(--muted); }

  .editor { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
  .head { display:flex; gap:10px; align-items:center; }
  .head .title { flex: 1; font-weight: 800; min-width: 0; }
  .status { font-size: 12px; color: var(--muted); min-width: 70px; text-align: right; }
  .back { display:none; background: transparent; border: 1px solid var(--border); color: var(--text); }

  .iconBtn { background: transparent; border: 1px solid var(--border); color: var(--text); padding: 6px 10px; border-radius: 10px; font-weight: 800; }
  /* dots (removed) */

  .trash { background: transparent; border: 1px solid rgba(255, 107, 107, 0.55); color: var(--danger); display:inline-flex; align-items:center; justify-content:center; }
  .trash:hover { filter: brightness(1.08); }
  .detailsRow { margin-top: 12px; display:grid; grid-template-columns: 1fr 220px; gap: 12px; align-items: start; }
  @media (max-width: 900px){ .detailsRow { grid-template-columns: 1fr; } }

  .shareCol { min-width: 0; }
  .groupCol { min-width: 0; }
  .groupCol select { width: 100%; }

  .shareScroll { max-height: 110px; overflow: auto; }
  .mdbar { margin-top: 10px; display:flex; gap: 6px; flex-wrap: wrap; }
  .mdBtn { background: transparent; border: 1px solid var(--border); color: var(--text); padding: 6px 8px; border-radius: 10px; font-weight: 800; }
  .mdBtn:hover { filter: brightness(1.08); }

  .body { width: 100%; min-height: 320px; margin-top: 10px; resize: vertical; }
  .preview { width: 100%; min-height: 320px; margin-top: 10px; border: 1px solid var(--border); border-radius: 12px; padding: 12px; box-sizing: border-box; background: rgba(255,255,255,0.02); overflow:auto; }
  .preview :global(*) { max-width: 100%; box-sizing: border-box; }
  .preview { overflow-wrap: anywhere; }
  .preview :global(h1), .preview :global(h2), .preview :global(h3) { margin: 14px 0 8px; }
  .preview :global(p) { margin: 10px 0; }
  .preview :global(code) { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 0.95em; padding: 1px 5px; border-radius: 6px; border: 1px solid var(--border); background: rgba(255,255,255,0.03); }
  .preview :global(pre) { padding: 10px; border-radius: 12px; border: 1px solid var(--border); background: rgba(0,0,0,0.25); overflow:auto; }
  .preview :global(a) { text-decoration: underline; }

  .share { margin-top: 10px; }
  .label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }

  .noteShare { margin-top: 10px; }
  .noteShareSummary { cursor: pointer; font-size: 12px; color: var(--muted); font-weight: 800; }

  .shareBox { display:flex; flex-direction:column; gap:6px; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: rgba(255,255,255,0.02); }
  .shareRow { display:flex; gap:8px; align-items:center; font-size: 13px; color: var(--text); }

  .err { margin-top: 10px; color: var(--danger); font-size: 13px; }
  .hint { margin-top: 8px; color: var(--muted); font-size: 12px; }
  .empty { color: var(--muted); padding: 20px; }

  .modalOverlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display:flex; align-items:center; justify-content:center; padding: 14px; z-index: 50; }
  .modal { width: min(520px, 100%); border: 1px solid var(--border); border-radius: 14px; background: var(--panel); padding: 12px; }
  .modalHead { display:flex; align-items:center; justify-content:space-between; gap: 10px; }
  .modalTitle { font-weight: 900; }
  .row2 { display:flex; gap: 10px; align-items:center; margin-top: 10px; color: var(--text); }
  .row3 { display:flex; flex-direction:column; gap: 6px; margin-top: 10px; }
  .row3 label { font-size: 12px; color: var(--muted); }
  .actions { display:flex; gap: 8px; margin-top: 12px; }
  .btnGhost { background: transparent; border: 1px solid var(--border); color: var(--text); }
</style>
