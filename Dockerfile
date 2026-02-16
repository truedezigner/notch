# Multi-stage build: Vite/Svelte frontend + FastAPI backend

FROM node:22-alpine AS web
WORKDIR /src
COPY web/package*.json /src/
RUN npm ci
COPY web /src
RUN npm run build

FROM python:3.12-slim AS api
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY api /app/api

# Copy built frontend into api/static
COPY --from=web /src/dist /app/api/static

ENV DB_PATH=/data/app.db
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
