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
  docker compose logs --tail=50 backend
  fail "Health check gagal pada port 3215"
}

run_migrations() {
  log "Run database migrations"
  cd "${DEPLOY_PATH}"

  # Pastikan container db sedang jalan (mungkin belum restart)
  docker compose up -d db
  docker compose exec -T db sh -c 'until pg_isready -U postgres; do sleep 1; done'

  # Jalankan ALTER TABLE via psql di container db.
  # IF NOT EXISTS / IF NOT EXISTS pattern — aman dijalankan berulang.
  docker compose exec -T db psql -U postgres -d uang_pengiriman -v ON_ERROR_STOP=0 <<'SQL'
-- migrate_custom_toll
ALTER TABLE customers ADD COLUMN IF NOT EXISTS custom_toll_breakdown TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS share_location TEXT;

-- migrate_customer_lock (is_locked -> is_locked_marketing + is_locked_finance)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name = 'is_locked'
  ) THEN
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'customers' AND column_name = 'is_locked_marketing'
    ) THEN
      ALTER TABLE customers DROP COLUMN is_locked;
    ELSE
      ALTER TABLE customers RENAME COLUMN is_locked TO is_locked_marketing;
    END IF;
  END IF;
END $$;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_locked_marketing BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_locked_finance BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name = 'updated_by_id'
  ) THEN
    ALTER TABLE customers ADD COLUMN updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
  END IF;
END $$;

-- migrate_uang_mel (buat tabel baru, tambah FK, drop kolom lama)
CREATE TABLE IF NOT EXISTS uang_mel_master (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  amount NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vehicle_types' AND column_name = 'uang_mel_id'
  ) THEN
    ALTER TABLE vehicle_types ADD COLUMN uang_mel_id BIGINT REFERENCES uang_mel_master(id) ON DELETE SET NULL;
  END IF;
END $$;
ALTER TABLE vehicle_types DROP COLUMN IF EXISTS uang_mel;
SQL

  # ---- Seed data: ruas tol Sumatera, ferry, dan FUSO 6 Roda Panjang ----
  docker compose exec -T db psql -U postgres -d uang_pengiriman -v ON_ERROR_STOP=0 <<'SQL'

-- ============================================================
-- Seed: Ruas Tol Sumatera & Penyeberangan Ferry
-- Aman dijalankan berulang (INSERT ... ON CONFLICT DO NOTHING)
-- ============================================================

-- 1. Penyeberangan Merak - Bakauheni
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Penyeberangan', 'Penyeberangan Merak - Bakauheni', 'Pelabuhan Merak', 'Pelabuhan Bakauheni', 30, 743800, 1225800, 0, true
WHERE NOT EXISTS (SELECT 1 FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni');

-- 2. Bakauheni - Terbanggi Besar
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jalan Tol Trans-Sumatera', 'Bakauheni - Terbanggi Besar', 'Bakauheni', 'Terbanggi Besar', 140, 170000, 220000, 0, true
WHERE NOT EXISTS (SELECT 1 FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar');

-- 3. Tambahkan tarif per golongan (toll_section_rates)
-- Golongan I
DO $$
DECLARE
  v_gol_id INTEGER;
  v_sec_id INTEGER;
BEGIN
  SELECT id INTO v_gol_id FROM toll_golongan WHERE code = 'I' LIMIT 1;
  IF v_gol_id IS NOT NULL THEN
    -- Ferry Gol I
    SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni' LIMIT 1;
    IF v_sec_id IS NOT NULL THEN
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec_id, v_gol_id, 481800)
      ON CONFLICT (section_id, golongan_id) DO NOTHING;
    END IF;
    -- Bakauheni-Terbanggi Gol I
    SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar' LIMIT 1;
    IF v_sec_id IS NOT NULL THEN
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec_id, v_gol_id, 118500)
      ON CONFLICT (section_id, golongan_id) DO NOTHING;
    END IF;
  END IF;
END $$;

-- Golongan II & III
DO $$
DECLARE
  v_gol_id INTEGER;
  v_sec_id INTEGER;
  v_code TEXT;
BEGIN
  FOR v_code IN SELECT unnest(ARRAY['II','III']) LOOP
    SELECT id INTO v_gol_id FROM toll_golongan WHERE code = v_code LIMIT 1;
    IF v_gol_id IS NOT NULL THEN
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 743800)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 170000)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
    END IF;
  END LOOP;
END $$;

-- Golongan IV & V
DO $$
DECLARE
  v_gol_id INTEGER;
  v_sec_id INTEGER;
  v_code TEXT;
BEGIN
  FOR v_code IN SELECT unnest(ARRAY['IV','V']) LOOP
    SELECT id INTO v_gol_id FROM toll_golongan WHERE code = v_code LIMIT 1;
    IF v_gol_id IS NOT NULL THEN
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 1225800)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 220000)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
    END IF;
  END LOOP;
END $$;

-- ============================================================
-- Seed: Jenis Kendaraan FUSO 6 Roda Panjang (Golongan IV)
-- ============================================================
DO $$
DECLARE
  v_gol_iv_id INTEGER;
  v_bbm_id INTEGER;
  v_uang_mel_id INTEGER;
  v_km_per_liter NUMERIC;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM vehicle_types WHERE name = 'FUSO 6 Roda Panjang') THEN
    SELECT id INTO v_gol_iv_id FROM toll_golongan WHERE code = 'IV' LIMIT 1;
    -- Ambil referensi dari FUSO yang sudah ada
    SELECT bbm_id, uang_mel_id, km_per_liter
      INTO v_bbm_id, v_uang_mel_id, v_km_per_liter
      FROM vehicle_types
      WHERE name ILIKE '%fuso%roda%'
      LIMIT 1;
    INSERT INTO vehicle_types (name, toll_golongan_id, bbm_id, uang_mel_id, km_per_liter)
    VALUES ('FUSO 6 Roda Panjang', v_gol_iv_id, v_bbm_id, v_uang_mel_id, v_km_per_liter);
  END IF;
END $$;

SQL

  log "Migrations done"
}

preflight
sync_code
build_frontend
run_migrations
restart_services
health_check
