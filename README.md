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

## Build container

```bash
docker build -t notch:0.1.0 .
```

## Deploy

See Portainer stacks in `/home/legend/.openclaw/workspace`:
- `portainer-ntfy.yml`
- `portainer-notes-todos.yml` (update image to GHCR tag)
