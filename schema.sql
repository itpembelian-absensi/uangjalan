-- Uang Pengiriman: Full PostgreSQL schema
-- Mencakup semua table yang dibutuhkan aplikasi
-- Jalankan: psql -U postgres -d uang_pengiriman -f schema.sql

BEGIN;

-- Master: Vehicle Brands
CREATE TABLE IF NOT EXISTS vehicle_brands (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master: BBM
CREATE TABLE IF NOT EXISTS bbm_master (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  price         NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master: Toll Golongan
CREATE TABLE IF NOT EXISTS toll_golongan (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  code          TEXT NOT NULL UNIQUE,
  description   TEXT,
  sort_order    INT NOT NULL DEFAULT 0,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master: Vehicle Types
CREATE TABLE IF NOT EXISTS vehicle_types (
  id              BIGSERIAL PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  toll_golongan_id BIGINT REFERENCES toll_golongan(id) ON DELETE SET NULL,
  bbm_id          BIGINT REFERENCES bbm_master(id) ON DELETE SET NULL,
  km_per_liter    NUMERIC(10,2),
  uang_mel        NUMERIC(14,2) NOT NULL DEFAULT 0
);

-- Master: Vehicles
CREATE TABLE IF NOT EXISTS vehicles (
  id              BIGSERIAL PRIMARY KEY,
  plate_number    TEXT NOT NULL UNIQUE,
  brand_id        BIGINT NOT NULL REFERENCES vehicle_brands(id) ON UPDATE CASCADE,
  type_id         BIGINT REFERENCES vehicle_types(id) ON UPDATE CASCADE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master: Drivers
CREATE TABLE IF NOT EXISTS drivers (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  phone         TEXT NULL,
  bank_name     TEXT NULL,
  bank_account  TEXT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master: Customers
CREATE TABLE IF NOT EXISTS customers (
  id            BIGSERIAL PRIMARY KEY,
  code          TEXT UNIQUE,
  name          TEXT NOT NULL,
  address       TEXT,
  kelurahan     TEXT,
  kecamatan     TEXT,
  city          TEXT,
  phone         TEXT,
  email         TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  vehicle_type_id BIGINT REFERENCES vehicle_types(id) ON DELETE SET NULL,
  uang_jalan    NUMERIC(14,2),
  latitude      NUMERIC(10,7),
  longitude     NUMERIC(10,7)
);

-- Master: Toll Sections
CREATE TABLE IF NOT EXISTS toll_sections (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  length_km     NUMERIC(10,2) NOT NULL DEFAULT 1,
  gol23         NUMERIC(14,2) NOT NULL,
  gol45         NUMERIC(14,2) NOT NULL,
  sort_order    INT NOT NULL DEFAULT 0,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Toll Section Rates
CREATE TABLE IF NOT EXISTS toll_section_rates (
  id            BIGSERIAL PRIMARY KEY,
  section_id    BIGINT NOT NULL REFERENCES toll_sections(id) ON DELETE CASCADE,
  golongan_id   BIGINT NOT NULL REFERENCES toll_golongan(id) ON DELETE CASCADE,
  rate          NUMERIC(14,2) NOT NULL DEFAULT 0,
  UNIQUE(section_id, golongan_id)
);

-- Customer Vehicle Tariffs
CREATE TABLE IF NOT EXISTS customer_vehicle_tariffs (
  id              BIGSERIAL PRIMARY KEY,
  customer_id     BIGINT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  vehicle_type_id BIGINT NOT NULL REFERENCES vehicle_types(id) ON DELETE CASCADE,
  uang_jalan      NUMERIC(14,2) NOT NULL DEFAULT 0,
  bbm             NUMERIC(14,2) NOT NULL DEFAULT 0,
  tol             NUMERIC(14,2) NOT NULL DEFAULT 0,
  parkir          NUMERIC(14,2) NOT NULL DEFAULT 0,
  lain_lain       NUMERIC(14,2) NOT NULL DEFAULT 0,
  uang_mel        NUMERIC(14,2) NOT NULL DEFAULT 0
);

-- Warehouse Settings
CREATE TABLE IF NOT EXISTS warehouse_settings (
  id            BIGINT PRIMARY KEY,
  name          TEXT NOT NULL DEFAULT 'Gudang Utama',
  address       TEXT,
  city          TEXT,
  latitude      NUMERIC(10,7),
  longitude     NUMERIC(10,7),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Users
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

-- Delivery Routes
CREATE TABLE IF NOT EXISTS delivery_routes (
  id              BIGSERIAL PRIMARY KEY,
  route_no        TEXT NOT NULL UNIQUE,
  date            DATE NOT NULL,
  vehicle_id      BIGINT REFERENCES vehicles(id) ON UPDATE CASCADE,
  driver_id       BIGINT REFERENCES drivers(id) ON UPDATE CASCADE,
  remarks         TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  vehicle_type_id BIGINT REFERENCES vehicle_types(id) ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_delivery_routes_date ON delivery_routes(date);

-- Delivery Route Stops
CREATE TABLE IF NOT EXISTS delivery_route_stops (
  id            BIGSERIAL PRIMARY KEY,
  route_id      BIGINT NOT NULL REFERENCES delivery_routes(id) ON DELETE CASCADE,
  customer_id   BIGINT NOT NULL REFERENCES customers(id) ON UPDATE CASCADE,
  sort_order    INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  description   TEXT,
  entity_code   VARCHAR(64),
  UNIQUE(route_id, customer_id)
);

-- Delivery Route Stop Lines
CREATE TABLE IF NOT EXISTS delivery_route_stop_lines (
  id            BIGSERIAL PRIMARY KEY,
  stop_id       BIGINT NOT NULL REFERENCES delivery_route_stops(id) ON DELETE CASCADE,
  item_name     TEXT NOT NULL,
  quantity      NUMERIC(12,3) NOT NULL,
  sort_order    INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sales (header)
CREATE TABLE IF NOT EXISTS sales (
  id                BIGSERIAL PRIMARY KEY,
  sale_no           TEXT NOT NULL UNIQUE,
  date              DATE NOT NULL,
  vehicle_id        BIGINT REFERENCES vehicles(id) ON UPDATE CASCADE,
  driver_id         BIGINT REFERENCES drivers(id) ON UPDATE CASCADE,
  remarks           TEXT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  extra_uang_jalan  NUMERIC(14,2) NOT NULL DEFAULT 0,
  delivery_route_id BIGINT REFERENCES delivery_routes(id) ON DELETE CASCADE,
  finance_paid_at   TIMESTAMPTZ,
  finance_paid_by   BIGINT REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);

-- Sale Details
CREATE TABLE IF NOT EXISTS sale_details (
  id                BIGSERIAL PRIMARY KEY,
  sale_id           BIGINT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  customer_id       BIGINT NOT NULL REFERENCES customers(id) ON UPDATE CASCADE,
  amount            NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  vehicle_type_id   BIGINT REFERENCES vehicle_types(id) ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sale_details_sale_id ON sale_details(sale_id);

-- Cash Disbursements
CREATE TABLE IF NOT EXISTS cash_disbursements (
  id                BIGSERIAL PRIMARY KEY,
  customer_id       BIGINT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  vehicle_type_id   BIGINT REFERENCES vehicle_types(id) ON DELETE SET NULL,
  amount            NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  description       TEXT NULL,
  disbursed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cash_disbursements_disbursed_at ON cash_disbursements(disbursed_at);

-- App Menus
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

-- Role Menu Access
CREATE TABLE IF NOT EXISTS role_menu_access (
  menu_id       TEXT NOT NULL REFERENCES app_menus(id) ON DELETE CASCADE,
  role          TEXT NOT NULL,
  access_level  TEXT NOT NULL CHECK (access_level IN ('full', 'read', 'none')),
  PRIMARY KEY (menu_id, role)
);
