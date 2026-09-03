# Notch

LAN-first notes + todos with per-user notifications via **ntfy**.

- Web UI: `/app/` (Svelte)
- API: `/api/*` (FastAPI)
- Reminders: background scheduler loop in the Notch API process

## Features (MVP+)

### Todos
- Multiple lists + “All” + “Trash”
- Title-only reminders (no description)
- Preview-first voice capture into a selected list
- Local smart splitting, duplicate removal, and optional category labels
- Assign, share-with, due, remind
- Deep links: `/app/todos/:id`
- Soft delete + undo

### Notes
- Groups + “All” + “Trash”
- Preview-first voice capture into a selected group
- Markdown editor + Preview
- Autosave
- Group-level share + note-level share
- Public editable share links (anyone-with-link) with optional expiry
- Deep links: `/app/notes/:id`
- Soft delete + undo

### Voice capture

Use **Voice add** from the Todos or Notes tab. Notch keeps the transcript editable and
does not create anything until the final Add button is pressed. Todo speech is split on
clear item boundaries (commas, “next item,” repeated intentions, sentence boundaries,
and independent action changes); connected phrases such as “phone charger and cable”
remain together. The interpreter refreshes while speech arrives and once more when
listening ends. Voice add defaults to the currently selected todo list or note group,
falling back to Inbox only from All/Trash. When categories are spoken out of order, the
preview offers to organize and label them before saving.

Speech recognition comes from the browser/device. Some browsers block microphone access
on a plain HTTP LAN address; the same preview works with the phone or keyboard dictation
button in the transcript field when that happens.

## Local dev (Zorin-96)

Backend:
```bash
cd api
../.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

Frontend:
```bash
cd web
npm run dev -- --host 0.0.0.0 --port 5173
```

## Bootstrap first user

Creates the first user if none exist (admin = first created user):

```bash
curl -sS -X POST http://localhost:8080/api/admin/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{"handle":"jon","display_name":"Jon","password":"REPLACE_ME"}'
```

## Build container (local)

```bash
docker build -t notch:0.1.0 .
```

## Ship (GHCR)

This repo includes a GitHub Actions workflow that builds & pushes to GHCR on:
- pushes to `main` (tag: `main`)
- tags like `v0.1.0`

Images:
- `ghcr.io/truedezigner/notch:<tag>`

## Deploy (Portainer)

Workspace stack files:
- Notch: `/home/legend/.openclaw/workspace/portainer-notes-todos.yml`
- ntfy:
  - **MVP open-LAN:** `/home/legend/.openclaw/workspace/portainer-ntfy-open.yml`
  - (Optional later) hardened/auth config

Default LAN ports:
- ntfy: `http://192.168.29.228:8082`
- Notch: `http://192.168.29.228:8083/app/`

### Native iOS live sync

The native app writes idempotent changes to `/api/ios/v1/operations`. A successful
write advances the process-local change revision and wakes authenticated foreground
clients waiting on `/api/ios/v1/changes`; those clients then fetch their normal
permission-filtered `/api/ios/v1/snapshot`. The notification contains no note or todo
content. Its 25-second long-poll timeout is only a keepalive, and native clients retain
periodic polling plus pull-to-refresh as recovery paths. Notch currently runs one
Uvicorn process, which is required by the process-local wake signal.

## Notes on ntfy auth

If ntfy is configured with `deny-all` by default, Notch must publish with an Authorization header. The current MVP path is to run ntfy open on LAN first, then harden later.
