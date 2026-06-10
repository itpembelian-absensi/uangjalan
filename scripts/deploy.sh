#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/srv/docker/uangjalan}"
BRANCH="${BRANCH:-main}"
ENV_FILE="${ENV_FILE:-.env}"
GIT_SHA="${GIT_SHA:-}"

log() {
  echo "==> $*"
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

preflight() {
  command -v docker >/dev/null || fail "docker tidak ditemukan"
  command -v npm >/dev/null || fail "npm tidak ditemukan"
  command -v git >/dev/null || fail "git tidak ditemukan"
  command -v curl >/dev/null || fail "curl tidak ditemukan"
  docker compose version >/dev/null || fail "docker compose tidak tersedia"

  [ -d "${DEPLOY_PATH}" ] || fail "Folder deploy tidak ada: ${DEPLOY_PATH}"
  [ -d "${DEPLOY_PATH}/.git" ] || fail "Bukan git repo: ${DEPLOY_PATH}"
  [ -f "${DEPLOY_PATH}/${ENV_FILE}" ] || fail "File ${ENV_FILE} tidak ada di ${DEPLOY_PATH}"

  local node_major
  node_major="$(node -p "process.versions.node.split('.')[0]")"
  [ "${node_major}" -ge 18 ] || fail "Node.js 18+ diperlukan, saat ini: $(node -v)"

  git config --global --add safe.directory "${DEPLOY_PATH}" 2>/dev/null || true
}

sync_code() {
  log "Sync code"
  cd "${DEPLOY_PATH}"

  git remote -v
  git fetch origin "${BRANCH}" --tags --force

  if [ -n "${GIT_SHA}" ]; then
    git fetch origin "${GIT_SHA}" --depth=1 2>/dev/null || true
    git reset --hard "${GIT_SHA}"
  else
    git reset --hard "origin/${BRANCH}"
  fi

  echo "Active commit: $(git log -1 --oneline)"
  if [ -n "${GIT_SHA}" ]; then
    local head_sha
    head_sha="$(git rev-parse HEAD)"
    [ "${head_sha}" = "${GIT_SHA}" ] || fail "HEAD (${head_sha}) != GIT_SHA (${GIT_SHA})"
  fi
}

build_frontend() {
  log "Build frontend"
  cd "${DEPLOY_PATH}/frontend"

  if [ -f package-lock.json ]; then
    npm ci --no-audit --no-fund
  else
    npm install --no-audit --no-fund
  fi

  export VITE_GIT_SHA="${GIT_SHA:-$(git -C "${DEPLOY_PATH}" rev-parse HEAD)}"
  npm run build

  [ -f dist/index.html ] || fail "frontend/dist/index.html tidak ditemukan setelah build"
  [ -n "$(find dist/assets -maxdepth 1 -name '*.js' -print -quit)" ] || fail "Bundle JS frontend kosong"

  local sha_short="${VITE_GIT_SHA:0:12}"
  grep -rq "${sha_short}" dist/assets/ || fail "Bundle frontend tidak memuat commit ${sha_short}"
  log "Frontend built (rev ${sha_short})"
}

restart_services() {
  log "Restart containers"
  cd "${DEPLOY_PATH}"
  docker compose up -d --force-recreate --remove-orphans
}

health_check() {
  log "Health check"
  sleep 5

  local i api_code frontend_ok=0
  for i in $(seq 1 30); do
    api_code="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3215/api/auth/me || true)"
    if curl -sf http://localhost:3215/ 2>/dev/null | grep -q 'id="root"'; then
      frontend_ok=1
    fi

    if { [ "${api_code}" = "200" ] || [ "${api_code}" = "401" ]; } && [ "${frontend_ok}" -eq 1 ]; then
      log "Deploy successful — API (${api_code}) + frontend OK on port 3215"
      docker compose ps
      return 0
    fi

    echo "Waiting for services... (${i}/30) api=${api_code:-000} frontend=${frontend_ok}"
    sleep 2
  done

  docker compose ps
  fail "Health check gagal pada port 3215"
}

preflight
sync_code
build_frontend
restart_services
health_check
