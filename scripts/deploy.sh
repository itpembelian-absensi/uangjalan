#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/srv/docker/uangjalan}"
BRANCH="${BRANCH:-main}"
ENV_FILE="${ENV_FILE:-.env}"

cd "$DEPLOY_PATH"

echo "==> Sync code"
git fetch origin "$BRANCH"
if [ -n "${GIT_SHA:-}" ]; then
  git reset --hard "$GIT_SHA"
else
  git reset --hard "origin/${BRANCH}"
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing ${ENV_FILE} in ${DEPLOY_PATH}" >&2
  echo "Copy .env.production.example to .env and fill in the values." >&2
  exit 1
fi

echo "==> Build frontend"
cd frontend
npm install
npm run build
cd "$DEPLOY_PATH"

echo "==> Restart containers"
docker compose up -d --force-recreate --remove-orphans

echo "==> Health check"
sleep 5
for i in $(seq 1 20); do
  if curl -s http://localhost:3215/api/auth/me > /dev/null 2>&1; then
    echo "Deploy successful — services ready on port 3215"
    docker compose ps
    exit 0
  fi
  echo "Waiting for backend... (${i}/20)"
  sleep 2
done

echo "Health check failed on port 3215" >&2
docker compose ps
exit 1
