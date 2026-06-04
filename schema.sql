-- Uang Pengiriman: PostgreSQL schema
-- Jalankan: psql -U postgres -d uang_pengiriman -f schema.sql

BEGIN;

-- Master
CREATE TABLE IF NOT EXISTS customers (
  id            BIGSERIAL PRIMARY KEY,
  code          TEXT UNIQUE,
  name          TEXT NOT NULL UNIQUE,
  address       TEXT,
  city          TEXT,
  phone         TEXT,
  email         TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicle_brands (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicle_types (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  uang_jalan    NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vehicles (
  id              BIGSERIAL PRIMARY KEY,
  plate_number    TEXT NOT NULL UNIQUE,
  brand_id        BIGINT NOT NULL REFERENCES vehicle_brands(id) ON UPDATE CASCADE,
  type_id         BIGINT REFERENCES vehicle_types(id) ON UPDATE CASCADE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS drivers (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  phone         TEXT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Transaksi Penjualan (header)
CREATE TABLE IF NOT EXISTS sales (
  id                BIGSERIAL PRIMARY KEY,
  sale_no           TEXT NOT NULL UNIQUE, -- nomor transaksi penjualan
  date              DATE NOT NULL,
  vehicle_id        BIGINT NOT NULL REFERENCES vehicles(id) ON UPDATE CASCADE,
  driver_id         BIGINT NOT NULL REFERENCES drivers(id) ON UPDATE CASCADE,
  remarks           TEXT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);

-- Transaksi Penjualan (detail)
CREATE TABLE IF NOT EXISTS sale_details (
  id                BIGSERIAL PRIMARY KEY,
  sale_id           BIGINT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  customer_id       BIGINT NOT NULL REFERENCES customers(id) ON UPDATE CASCADE,
  amount            NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sale_details_sale_id ON sale_details(sale_id);

-- Pengeluaran uang pengiriman (bisa lebih dari 1 per penjualan)
CREATE TABLE IF NOT EXISTS cash_disbursements (
  id                BIGSERIAL PRIMARY KEY,
  customer_id       BIGINT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  vehicle_type_id   BIGINT REFERENCES vehicle_types(id) ON DELETE SET NULL,
  amount            NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  description       TEXT NULL,
  disbursed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cash_disbursements_delivery_note ON cash_disbursements(delivery_note_id);
CREATE INDEX IF NOT EXISTS idx_cash_disbursements_disbursed_at ON cash_disbursements(disbursed_at);

-- Users & role-based access
CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  full_name     TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'marketing',
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Matriks akses per menu (dapat diedit Admin dari aplikasi)
CREATE TABLE IF NOT EXISTS app_menus (
  id              TEXT PRIMARY KEY,
  label           TEXT NOT NULL,
  path            TEXT NOT NULL,
  section         TEXT NOT NULL,
  icon            TEXT NOT NULL,
  sort_order      INT NOT NULL DEFAULT 0,
  read_permission TEXT NOT NULL,
  write_permission TEXT
);

CREATE TABLE IF NOT EXISTS role_menu_access (
  menu_id       TEXT NOT NULL REFERENCES app_menus(id) ON DELETE CASCADE,
  role          TEXT NOT NULL,
  access_level  TEXT NOT NULL CHECK (access_level IN ('full', 'read', 'none')),
  PRIMARY KEY (menu_id, role)
);

COMMIT;

