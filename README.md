# Notch

LAN-first notes + todos with per-user notifications via **ntfy**.

- Web UI: `/app/` (Svelte)
- API: `/api/*` (FastAPI)
- Reminders: background scheduler loop in the Notch API process

## Features (MVP+)

### Todos
- Multiple lists + “All” + “Trash”
- Title-only reminders (no description)
- Assign, share-with, due, remind
- Deep links: `/app/todos/:id`
- Soft delete + undo

### Notes
- Groups + “All” + “Trash”
- Markdown editor + Preview
- Autosave
- Group-level share + note-level share
- Public editable share links (anyone-with-link) with optional expiry
- Deep links: `/app/notes/:id`
- Soft delete + undo

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

## Notes on ntfy auth

If ntfy is configured with `deny-all` by default, Notch must publish with an Authorization header. The current MVP path is to run ntfy open on LAN first, then harden later.
