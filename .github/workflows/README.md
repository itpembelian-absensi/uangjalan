# CI/CD - Self-hosted Runner

## Setup

### 1. Self-hosted Runner
Di GitHub repo: **Settings > Actions > Runners > New self-hosted runner**

Requirement di server:
- Docker & Docker Compose
- Itu saja

### 2. GitHub Secrets
Buka **Settings > Secrets and variables > Actions**, tambahkan:

| Secret             | Contoh             | Keterangan          |
|--------------------|--------------------|---------------------|
| DB_PASSWORD        | strong-pg-pass     | Password PostgreSQL |
| SESSION_SECRET     | random-string-32   | Session encryption  |
| ADMIN_USERNAME     | admin              | Default admin user  |
| ADMIN_PASSWORD     | secure-pass        | Default admin pass  |
| GOOGLE_MAPS_API_KEY| (opsional)         | Google Maps API     |

## Arsitektur

```
Port 3215 (publish)
    │
    ▼
  Caddy (reverse proxy)
    ├── /api/*  ──▶ backend:8000
    ├── /auth/* ──▶ backend:8000
    ├── /ui/*   ──▶ backend:8000
    └── /*      ──▶ frontend:80 (nginx + static)
                         │
  backend ──────────────▶ db:5432 (PostgreSQL)
```

## Port

Hanya **1 port yang di-publish**: `3215`

Semua service lain berkomunikasi lewat Docker network internal.

## Cara Deploy

**Otomatis:** push ke `main`
**Manual:** tab Actions > Deploy > Run workflow

## Build

- Backend: `python:3.11-slim` + pip install (cepat, <30s)
- Frontend: `node:20-alpine` multi-stage → `nginx:alpine` (serve static)
- DB & Caddy: official image, tanpa build

## Koneksi dari Reverse Proxy Eksternal

Karena kamu sudah punya reverse proxy di server lain, cukup arahkan ke `http://<server-ip>:3215`. Caddy di sini handle routing internal saja, tidak perlu SSL — biarkan reverse proxy eksternal yang urus itu.
