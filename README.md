# Notch

Self-hosted notes + todos with per-user notifications via **ntfy**.

## Dev (Zorin-96)

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

After the first run, images will appear at:
- `ghcr.io/truedezigner/notch:<tag>`

## Deploy

See Portainer stacks in `/home/legend/.openclaw/workspace`:
- `portainer-ntfy.yml`
- `portainer-notes-todos.yml` (set image to a pinned GHCR tag)
