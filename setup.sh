#!/bin/bash
set -e

echo "=== Uang Jalan - First Time Setup ==="
echo ""

# 1. Check prerequisites
echo "[1/5] Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not installed"; exit 1; }
command -v docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose not available"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not installed (need v20+)"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not installed"; exit 1; }
echo "OK"

# 2. Setup .env
echo ""
echo "[2/5] Setting up .env..."
if [ ! -f .env ]; then
  cp .env.production.example .env
  echo "Created .env from template."
  echo ">>> IMPORTANT: Edit .env and fill in your passwords! <<<"
  echo ""
  read -p "Press Enter after you've edited .env (or Ctrl+C to abort)..."
else
  echo ".env already exists, skipping."
fi

# 3. Build frontend
echo ""
echo "[3/5] Building frontend..."
cd frontend
npm install
npm run build
cd ..
echo "Frontend built -> frontend/dist/"

# 4. Start containers
echo ""
echo "[4/5] Starting Docker containers..."
docker compose up -d

# 5. Wait & verify
echo ""
echo "[5/5] Waiting for services..."
sleep 5
for i in $(seq 1 20); do
  if curl -s http://localhost:3215/api/auth/me > /dev/null 2>&1; then
    echo "Services ready!"
    break
  fi
  sleep 2
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  App:  http://localhost:3215"
echo "  DB:   localhost:5432 (internal) / via docker exec uangjalan-db psql"
echo ""
echo "  Default login: admin / (password in .env)"
echo ""
docker compose ps
