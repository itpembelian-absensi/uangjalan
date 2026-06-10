# CI/CD - Self-hosted Runner

## Setup

### 1. Self-hosted Runner
Di GitHub repo: **Settings > Actions > Runners > New self-hosted runner**

Label runner minimal: **`self-hosted`** (label `uangjalan` opsional).

Requirement di server:
- Docker & Docker Compose
- Node.js 20+ & npm
- Git & curl

### 2. File `.env` di server

Sama seperti **sjsstore**: `.env` tetap di **`/srv/docker/uangjalan/.env`** (tidak perlu dipindah).

```bash
cd /srv/docker/uangjalan
cp .env.production.example .env
nano .env
chmod 600 .env
```

Deploy memakai `scripts/deploy.sh` → `git reset --hard` di folder deploy. **Tidak** pakai `actions/checkout`, jadi `git clean` tidak jalan dan `.env` tidak terhapus.

> Kenapa workflow lama bermasalah? `actions/checkout` menjalankan `git clean -ffdx` yang menghapus file untracked (termasuk `.env` di-ignore). sjsstore dari awal sudah hindari itu dengan deploy langsung ke path tetap.

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

**Otomatis:** push ke `main` (workflow `.github/workflows/deploy.yml`)

**Manual:** tab Actions > Deploy > Run workflow

**Manual di server (jika CI gagal):**
```bash
cd /srv/docker/uangjalan
GIT_SHA=$(git rev-parse origin/main) bash scripts/deploy.sh
```

## Build

- Backend: `python:3.11-slim` + pip install (cepat, <30s)
- Frontend: `node:20-alpine` multi-stage → `nginx:alpine` (serve static)
- DB & Caddy: official image, tanpa build

## Koneksi dari Reverse Proxy Eksternal

Karena kamu sudah punya reverse proxy di server lain, cukup arahkan ke `http://<server-ip>:3215`. Caddy di sini handle routing internal saja, tidak perlu SSL — biarkan reverse proxy eksternal yang urus itu.
