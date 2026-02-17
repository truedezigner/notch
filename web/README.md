# Notch Web (Svelte + Vite)

This is the Notch frontend (Svelte 5 + Vite).

## Dev

```bash
cd web
npm run dev -- --host 0.0.0.0 --port 5173
```

## Build

```bash
cd web
npm run build
```

The production build output is served by the FastAPI container under `/app/*`.

## Notes

- Keep UI mobile-first.
- Avoid heavy dependencies; prefer simple components.
- Deep links:
  - `/app/todos/:id`
  - `/app/notes/:id`
