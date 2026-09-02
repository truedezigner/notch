<script lang="ts">
  import { onMount } from 'svelte';
  import { createTodo, listLists, type TodoList } from './api';
  import { createNote, listNoteGroups, type NoteGroup } from './notes_api';
  import {
    VOICE_CATEGORIES,
    encodedTodoTitle,
    needsCategoryOrganization,
    organizeByCategory,
    parseSpokenNote,
    parseTodoSpeech
  } from './voice-parser.js';

  export let defaultMode: 'todo' | 'note' = 'todo';
  export let onSaved: () => void = () => {};

  let open = false;
  let mode: 'todo' | 'note' = 'todo';
  let transcript = '';
  let todoItems: { title: string; category: string }[] = [];
  let lists: TodoList[] = [];
  let groups: NoteGroup[] = [];
  let targetListId = '';
  let targetGroupId = '';
  let noteTitle = '';
  let noteBody = '';
  let listening = false;
  let speechSupported = false;
  let secureContext = true;
  let recognition: any = null;
  let saving = false;
  let err: string | null = null;
  let status = '';
  let organize = false;
  let organizationSuggested = false;
  let addCategoryLabels = true;

  onMount(() => {
    speechSupported = Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
    secureContext = window.isSecureContext;
  });

  async function show() {
    open = true;
    mode = defaultMode;
    transcript = '';
    todoItems = [];
    noteTitle = '';
    noteBody = '';
    err = null;
    status = '';
    organize = false;
    organizationSuggested = false;
    try {
      [lists, groups] = await Promise.all([listLists(), listNoteGroups()]);
      const inbox = lists.find((list) => list.name.toLowerCase() === 'inbox');
      targetListId = inbox?.id || lists[0]?.id || '';
      targetGroupId = '';
    } catch (e: any) {
      err = e?.message || String(e);
    }
  }

  function close() {
    stopListening();
    open = false;
  }

  function rebuildPreview() {
    err = null;
    if (mode === 'todo') {
      todoItems = parseTodoSpeech(transcript);
      organizationSuggested = needsCategoryOrganization(todoItems);
      organize = organizationSuggested;
    } else {
      const note = parseSpokenNote(transcript);
      noteTitle = note.title;
      noteBody = note.body;
    }
  }

  function setMode(nextMode: 'todo' | 'note') {
    mode = nextMode;
    rebuildPreview();
  }

  function updateItem(index: number, patch: { title?: string; category?: string }) {
    todoItems = todoItems.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item);
  }

  function removeItem(index: number) {
    todoItems = todoItems.filter((_, itemIndex) => itemIndex !== index);
  }

  function startListening() {
    err = null;
    if (!speechSupported) {
      err = 'Voice recognition is not available in this browser. Use the transcript box with your keyboard microphone instead.';
      return;
    }
    const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = navigator.language || 'en-US';
    recognition.onresult = (event: any) => {
      let heard = '';
      for (let resultIndex = 0; resultIndex < event.results.length; resultIndex += 1) {
        heard += `${event.results[resultIndex][0].transcript} `;
      }
      transcript = heard.trim();
      rebuildPreview();
    };
    recognition.onerror = (event: any) => {
      listening = false;
      err = event.error === 'not-allowed'
        ? 'Microphone access was blocked. Allow microphone access, or use your keyboard microphone in the transcript box.'
        : `Voice recognition stopped: ${event.error || 'unknown error'}`;
    };
    recognition.onend = () => {
      listening = false;
      rebuildPreview();
    };
    try {
      recognition.start();
      listening = true;
    } catch (e: any) {
      err = e?.message || String(e);
      listening = false;
    }
  }

  function stopListening() {
    if (recognition) {
      try { recognition.stop(); } catch { /* already stopped */ }
      recognition = null;
    }
    listening = false;
  }

  async function save() {
    err = null;
    status = '';
    saving = true;
    try {
      if (mode === 'note') {
        if (!noteTitle.trim() || !noteBody.trim()) throw new Error('Add a title and note text first.');
        await createNote(noteTitle.trim(), targetGroupId || null, noteBody.trim());
        status = 'Voice note added';
        onSaved();
        close();
        return;
      }

      if (!targetListId) throw new Error('Choose a destination list.');
      let pending = todoItems.filter((item) => item.title.trim());
      if (!pending.length) throw new Error('No todo items are ready to add.');
      if (organize) pending = organizeByCategory(pending);

      let created = 0;
      const failed: typeof pending = [];
      for (const item of pending) {
        try {
          await createTodo(encodedTodoTitle(item, organize && addCategoryLabels), targetListId);
          created += 1;
        } catch {
          failed.push(item);
        }
      }

      onSaved();
      if (failed.length) {
        todoItems = failed;
        err = `Added ${created}; ${failed.length} item${failed.length === 1 ? '' : 's'} could not be added and remain in this preview.`;
      } else {
        status = `Added ${created} item${created === 1 ? '' : 's'}`;
        close();
      }
    } catch (e: any) {
      err = e?.message || String(e);
    } finally {
      saving = false;
    }
  }
</script>

<button class="voiceLaunch" type="button" on:click={show} title="Add by voice" aria-label="Add by voice">
  <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
    <path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm-1-9a1 1 0 1 1 2 0v6a1 1 0 1 1-2 0V5Zm7 6a6 6 0 0 1-5 5.91V20h3v2H8v-2h3v-3.09A6 6 0 0 1 6 11h2a4 4 0 0 0 8 0h2Z" />
  </svg>
  Voice add
</button>

{#if status}
  <div class="voiceToast" role="status">{status}</div>
{/if}

{#if open}
  <div class="overlay" role="presentation" on:click={(event) => event.currentTarget === event.target && close()}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="voice-title">
      <div class="dialogHead">
        <div>
          <div class="eyebrow">VOICE CAPTURE</div>
          <h3 id="voice-title">Add to Notch</h3>
        </div>
        <button class="closeBtn" type="button" on:click={close} aria-label="Close">×</button>
      </div>

      <div class="modeSwitch" aria-label="What to add">
        <button type="button" class:active={mode === 'todo'} on:click={() => setMode('todo')}>Todo items</button>
        <button type="button" class:active={mode === 'note'} on:click={() => setMode('note')}>Note</button>
      </div>

      <div class="recordRow">
        {#if listening}
          <button class="record recording" type="button" on:click={stopListening}>
            <span class="recordDot"></span> Stop listening
          </button>
        {:else}
          <button class="record" type="button" on:click={startListening} disabled={!speechSupported}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm6-3a6 6 0 0 1-5 5.91V20h3v2H8v-2h3v-3.09A6 6 0 0 1 6 11h2a4 4 0 0 0 8 0h2Z" /></svg>
            Start listening
          </button>
        {/if}
        <span class="privacy">Your browser handles speech recognition. Notch saves nothing until you confirm.</span>
      </div>

      {#if !secureContext}
        <div class="notice">This local HTTP address may block browser microphone access. If it does, tap the transcript box and use your phone or keyboard’s dictation microphone.</div>
      {/if}

      <label class="field">
        <span>Transcript</span>
        <textarea bind:value={transcript} on:input={rebuildPreview} rows="4" placeholder={mode === 'todo' ? 'Example: shirts, toothbrush and toothpaste, phone charger, kids snacks' : 'Speak or type the note here…'}></textarea>
      </label>

      {#if mode === 'todo'}
        <label class="field">
          <span>Destination list</span>
          <select bind:value={targetListId}>
            {#each lists as list}
              <option value={list.id}>{list.name}</option>
            {/each}
          </select>
        </label>

        {#if organizationSuggested}
          <div class="organizeAsk">
            <strong>Your items jump between categories.</strong>
            <span>Would you like Notch to organize the preview by category?</span>
          </div>
        {/if}

        {#if todoItems.length}
          <div class="options">
            <label><input type="checkbox" bind:checked={organize} /> Organize by category</label>
            {#if organize}
              <label><input type="checkbox" bind:checked={addCategoryLabels} /> Keep category labels on saved items</label>
            {/if}
          </div>
          <div class="previewHead"><span>Review before adding</span><span>{todoItems.length} item{todoItems.length === 1 ? '' : 's'}</span></div>
          <div class="items">
            {#each (organize ? organizeByCategory(todoItems) : todoItems) as item}
              {@const originalIndex = todoItems.indexOf(item)}
              <div class="item">
                <input value={item.title} aria-label="Todo title" on:input={(event) => updateItem(originalIndex, { title: event.currentTarget.value })} />
                <select value={item.category} aria-label="Todo category" on:change={(event) => updateItem(originalIndex, { category: event.currentTarget.value })}>
                  {#each VOICE_CATEGORIES as category}
                    <option value={category}>{category}</option>
                  {/each}
                </select>
                <button type="button" class="remove" on:click={() => removeItem(originalIndex)} aria-label="Remove item">×</button>
              </div>
            {/each}
          </div>
        {:else if transcript.trim()}
          <div class="notice">I could not find a complete item yet. Separate items with “next item,” a comma, or a short pause.</div>
        {/if}
      {:else}
        <label class="field">
          <span>Note group</span>
          <select bind:value={targetGroupId}>
            <option value="">Inbox / no group</option>
            {#each groups as group}
              <option value={group.id}>{group.name}</option>
            {/each}
          </select>
        </label>
        <label class="field">
          <span>Title</span>
          <input bind:value={noteTitle} placeholder="Voice note title" />
        </label>
        <label class="field">
          <span>Note</span>
          <textarea bind:value={noteBody} rows="7" placeholder="Your note…"></textarea>
        </label>
      {/if}

      {#if err}<div class="error" role="alert">{err}</div>{/if}

      <div class="actions">
        <button class="cancel" type="button" on:click={close}>Cancel</button>
        <button type="button" on:click={save} disabled={saving || (mode === 'todo' ? !targetListId || !todoItems.length : !noteTitle.trim() || !noteBody.trim())}>
          {saving ? 'Adding…' : mode === 'todo' ? `Add ${todoItems.length || ''} item${todoItems.length === 1 ? '' : 's'}` : 'Add note'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .voiceLaunch { display:inline-flex; align-items:center; gap:7px; padding:10px 12px; border-radius:10px; border:1px solid rgba(93, 188, 255, .5); background:rgba(93, 188, 255, .1); color:var(--text); font-weight:800; }
  .voiceLaunch:hover { filter:brightness(1.1); }
  .overlay { position:fixed; inset:0; z-index:100; display:flex; align-items:center; justify-content:center; padding:14px; background:rgba(2, 6, 12, .72); backdrop-filter:blur(5px); }
  .dialog { width:min(690px, 100%); max-height:calc(100vh - 28px); overflow:auto; box-sizing:border-box; border:1px solid var(--border); border-radius:18px; background:#111922; color:var(--text); padding:18px; box-shadow:0 24px 80px rgba(0,0,0,.5); }
  .dialogHead { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
  .dialogHead h3 { margin:2px 0 0; font-size:23px; }
  .eyebrow { font-size:11px; font-weight:900; letter-spacing:.14em; color:#78c7ff; }
  .closeBtn, .remove { border:1px solid var(--border); background:transparent; color:var(--muted); }
  .closeBtn { width:38px; height:38px; padding:0; font-size:24px; }
  .modeSwitch { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin:18px 0 14px; padding:4px; border:1px solid var(--border); border-radius:12px; background:rgba(255,255,255,.025); }
  .modeSwitch button { border:0; background:transparent; color:var(--muted); }
  .modeSwitch button.active { background:var(--btn); color:var(--btnText); }
  .recordRow { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .record { display:inline-flex; align-items:center; gap:8px; }
  .record.recording { border-color:#ff6969; background:rgba(255, 105, 105, .14); color:#ff9494; }
  .recordDot { width:9px; height:9px; border-radius:50%; background:#ff6969; box-shadow:0 0 0 5px rgba(255,105,105,.12); }
  .privacy { font-size:12px; color:var(--muted); }
  .notice, .organizeAsk { margin-top:12px; padding:10px 12px; border-radius:11px; font-size:13px; line-height:1.45; }
  .notice { border:1px solid rgba(255, 199, 88, .3); background:rgba(255, 199, 88, .07); color:#f1d69d; }
  .organizeAsk { display:flex; flex-direction:column; gap:3px; border:1px solid rgba(93,188,255,.35); background:rgba(93,188,255,.08); }
  .field { display:flex; flex-direction:column; gap:6px; margin-top:13px; }
  .field > span, .previewHead { font-size:12px; font-weight:800; color:var(--muted); }
  input, textarea, select { width:100%; box-sizing:border-box; padding:10px 11px; border-radius:10px; border:1px solid var(--border); background:#0b1118; color:var(--text); font:inherit; }
  textarea { resize:vertical; line-height:1.45; }
  .options { display:flex; flex-direction:column; gap:7px; margin-top:13px; }
  .options label { display:flex; align-items:center; gap:8px; font-size:13px; }
  .options input { width:auto; }
  .previewHead { display:flex; justify-content:space-between; margin:15px 0 7px; }
  .items { display:flex; flex-direction:column; gap:7px; }
  .item { display:grid; grid-template-columns:minmax(0, 1fr) 145px 38px; gap:7px; }
  .remove { padding:0; font-size:20px; }
  .error { margin-top:12px; color:var(--danger); font-size:13px; }
  .actions { display:flex; justify-content:flex-end; gap:8px; margin-top:18px; padding-top:14px; border-top:1px solid var(--border); }
  .actions button { padding:10px 13px; border-radius:10px; border:1px solid var(--btn); background:var(--btn); color:var(--btnText); font-weight:800; }
  .actions button:disabled, .record:disabled { opacity:.45; }
  .actions .cancel { border-color:var(--border); background:transparent; color:var(--text); }
  .voiceToast { position:fixed; right:18px; bottom:18px; z-index:110; padding:10px 13px; border:1px solid var(--border); border-radius:999px; background:var(--panel); color:var(--text); }
  @media (max-width:560px) {
    .dialog { padding:14px; }
    .item { grid-template-columns:minmax(0, 1fr) 38px; }
    .item select { grid-column:1 / 2; grid-row:2; }
    .item .remove { grid-column:2; grid-row:1 / span 2; }
  }
</style>
