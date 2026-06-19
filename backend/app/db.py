from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.security import hash_password

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_schema() -> None:
    """Terapkan migrasi ringan yang dibutuhkan aplikasi."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE sale_details
                ADD COLUMN IF NOT EXISTS vehicle_type_id BIGINT
                REFERENCES vehicle_types(id) ON UPDATE CASCADE
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ADD COLUMN IF NOT EXISTS extra_uang_jalan NUMERIC(14,2) NOT NULL DEFAULT 0
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE customers
                ADD COLUMN IF NOT EXISTS latitude NUMERIC(10,7),
                ADD COLUMN IF NOT EXISTS longitude NUMERIC(10,7),
                ADD COLUMN IF NOT EXISTS share_location TEXT,
                ADD COLUMN IF NOT EXISTS force_toll BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE customers
                DROP CONSTRAINT IF EXISTS customers_name_key
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse_settings (
                  id BIGINT PRIMARY KEY,
                  name TEXT NOT NULL DEFAULT 'Gudang Utama',
                  address TEXT,
                  city TEXT,
                  latitude NUMERIC(10,7),
                  longitude NUMERIC(10,7),
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO warehouse_settings (id, name)
                VALUES (1, 'Gudang Utama')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS toll_sections (
                  id BIGSERIAL PRIMARY KEY,
                  name TEXT NOT NULL,
                  length_km NUMERIC(10,2) NOT NULL DEFAULT 1,
                  gol23 NUMERIC(14,2) NOT NULL,
                  gol45 NUMERIC(14,2) NOT NULL,
                  sort_order INT NOT NULL DEFAULT 0,
                  is_active BOOLEAN NOT NULL DEFAULT TRUE,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO toll_sections (name, length_km, gol23, gol45, sort_order)
                SELECT v.name, v.length_km, v.gol23, v.gol45, v.sort_order
                FROM (VALUES
                  ('Japek (Jakarta–Cikampek)', 73, 40500, 54000, 1),
                  ('JORR', 32, 25000, 33500, 2),
                  ('Dalam Kota & Sedyatmo', 15, 16500, 19000, 3),
                  ('Jagorawi', 45, 12000, 17000, 4)
                ) AS v(name, length_km, gol23, gol45, sort_order)
                WHERE NOT EXISTS (SELECT 1 FROM toll_sections LIMIT 1)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS toll_golongan (
                  id BIGSERIAL PRIMARY KEY,
                  name TEXT NOT NULL,
                  code TEXT NOT NULL UNIQUE,
                  description TEXT,
                  sort_order INT NOT NULL DEFAULT 0,
                  is_active BOOLEAN NOT NULL DEFAULT TRUE,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS toll_section_rates (
                  id BIGSERIAL PRIMARY KEY,
                  section_id BIGINT NOT NULL REFERENCES toll_sections(id) ON DELETE CASCADE,
                  golongan_id BIGINT NOT NULL REFERENCES toll_golongan(id) ON DELETE CASCADE,
                  rate NUMERIC(14,2) NOT NULL DEFAULT 0,
                  UNIQUE(section_id, golongan_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO toll_golongan (name, code, description, sort_order)
                SELECT v.name, v.code, v.description, v.sort_order
                FROM (VALUES
                  ('Golongan II', 'II', 'Truk 2 gandar (engkel, box, dll.)', 1),
                  ('Golongan III', 'III', 'Truk 3 gandar (tronton)', 2),
                  ('Golongan IV', 'IV', 'Truk 4 gandar', 3),
                  ('Golongan V', 'V', 'Truk 5 gandar atau lebih (trailer/gandeng)', 4)
                ) AS v(name, code, description, sort_order)
                WHERE NOT EXISTS (SELECT 1 FROM toll_golongan LIMIT 1)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO toll_section_rates (section_id, golongan_id, rate)
                SELECT ts.id, tg.id,
                  CASE
                    WHEN tg.code IN ('II', 'III') THEN ts.gol23
                    ELSE ts.gol45
                  END
                FROM toll_sections ts
                CROSS JOIN toll_golongan tg
                WHERE NOT EXISTS (SELECT 1 FROM toll_section_rates LIMIT 1)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE toll_sections
                ADD COLUMN IF NOT EXISTS network TEXT,
                ADD COLUMN IF NOT EXISTS origin_name TEXT,
                ADD COLUMN IF NOT EXISTS destination_name TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE toll_sections
                SET network = 'Jabodetabek'
                WHERE network IS NULL OR TRIM(network) = ''
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO toll_golongan (name, code, description, sort_order)
                SELECT 'Golongan I', 'I', 'Kendaraan ringan (mobil, motor)', 0
                WHERE NOT EXISTS (SELECT 1 FROM toll_golongan WHERE code = 'I')
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS toll_gates (
                  id BIGSERIAL PRIMARY KEY,
                  section_id BIGINT NOT NULL REFERENCES toll_sections(id) ON DELETE CASCADE,
                  code TEXT NOT NULL,
                  name TEXT NOT NULL,
                  latitude NUMERIC(10,7),
                  longitude NUMERIC(10,7),
                  sort_order INT NOT NULL DEFAULT 0,
                  is_active BOOLEAN NOT NULL DEFAULT TRUE,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  UNIQUE(section_id, code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_toll_gates_section ON toll_gates(section_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS toll_gate_fares (
                  id BIGSERIAL PRIMARY KEY,
                  entry_gate_id BIGINT NOT NULL REFERENCES toll_gates(id) ON DELETE CASCADE,
                  exit_gate_id BIGINT NOT NULL REFERENCES toll_gates(id) ON DELETE CASCADE,
                  golongan_id BIGINT NOT NULL REFERENCES toll_golongan(id) ON DELETE CASCADE,
                  rate NUMERIC(14,2) NOT NULL DEFAULT 0,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  UNIQUE(entry_gate_id, exit_gate_id, golongan_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE vehicle_types
                ADD COLUMN IF NOT EXISTS toll_golongan_id BIGINT
                REFERENCES toll_golongan(id) ON DELETE SET NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE vehicle_types vt
                SET toll_golongan_id = tg.id
                FROM toll_golongan tg
                WHERE vt.toll_golongan_id IS NULL
                  AND LOWER(vt.name) LIKE '%tronton%'
                  AND tg.code = 'III'
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE vehicle_types vt
                SET toll_golongan_id = tg.id
                FROM toll_golongan tg
                WHERE vt.toll_golongan_id IS NULL
                  AND tg.code = 'II'
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE sale_details sd
                SET vehicle_type_id = sub.vehicle_type_id
                FROM (
                    SELECT sd2.id AS sale_detail_id,
                           MIN(cvt.vehicle_type_id) AS vehicle_type_id
                    FROM sale_details sd2
                    JOIN customer_vehicle_tariffs cvt
                      ON cvt.customer_id = sd2.customer_id
                     AND cvt.uang_jalan = sd2.amount
                    WHERE sd2.vehicle_type_id IS NULL
                    GROUP BY sd2.id
                    HAVING COUNT(*) = 1
                ) sub
                WHERE sd.id = sub.sale_detail_id
                  AND sd.vehicle_type_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS bbm_master (
                  id BIGSERIAL PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  price NUMERIC(14,2) NOT NULL DEFAULT 0,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO bbm_master (name, price)
                SELECT v.name, v.price
                FROM (VALUES
                  ('Solar/Biosolar', 6800),
                  ('Pertamina Dex', 13200),
                  ('Pertamax', 13500)
                ) AS v(name, price)
                WHERE NOT EXISTS (SELECT 1 FROM bbm_master LIMIT 1)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE vehicle_types
                ADD COLUMN IF NOT EXISTS bbm_id BIGINT
                REFERENCES bbm_master(id) ON DELETE SET NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE vehicle_types vt
                SET bbm_id = bm.id
                FROM bbm_master bm
                WHERE vt.bbm_id IS NULL
                  AND bm.name = 'Solar/Biosolar'
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE vehicle_types
                ADD COLUMN IF NOT EXISTS km_per_liter NUMERIC(10,2)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE customer_vehicle_tariffs
                ADD COLUMN IF NOT EXISTS bbm NUMERIC(14,2) NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS tol NUMERIC(14,2) NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS parkir NUMERIC(14,2) NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS lain_lain NUMERIC(14,2) NOT NULL DEFAULT 0
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE customer_vehicle_tariffs
                ADD COLUMN IF NOT EXISTS uang_mel NUMERIC(14,2) NOT NULL DEFAULT 0
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'vehicle_types' AND column_name = 'uang_mel'
                  ) THEN
                    UPDATE customer_vehicle_tariffs cvt
                    SET uang_mel = COALESCE(vt.uang_mel, 0)
                    FROM vehicle_types vt
                    WHERE cvt.vehicle_type_id = vt.id
                      AND cvt.uang_mel = 0
                      AND COALESCE(vt.uang_mel, 0) > 0;
                  END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE customer_vehicle_tariffs
                SET uang_jalan = bbm + tol + uang_mel + parkir + lain_lain
                WHERE bbm + tol + uang_mel + parkir + lain_lain > 0
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS delivery_routes (
                  id BIGSERIAL PRIMARY KEY,
                  route_no TEXT NOT NULL UNIQUE,
                  date DATE NOT NULL,
                  vehicle_id BIGINT NOT NULL REFERENCES vehicles(id) ON UPDATE CASCADE,
                  driver_id BIGINT NOT NULL REFERENCES drivers(id) ON UPDATE CASCADE,
                  remarks TEXT,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_routes_date
                ON delivery_routes(date)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_routes_vehicle
                ON delivery_routes(vehicle_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS delivery_route_stops (
                  id BIGSERIAL PRIMARY KEY,
                  route_id BIGINT NOT NULL REFERENCES delivery_routes(id) ON DELETE CASCADE,
                  customer_id BIGINT NOT NULL REFERENCES customers(id) ON UPDATE CASCADE,
                  sort_order INT NOT NULL DEFAULT 0,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_route_stops_route
                ON delivery_route_stops(route_id)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_route_stops
                ADD COLUMN IF NOT EXISTS description TEXT
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_route_stops
                ADD COLUMN IF NOT EXISTS entity_code VARCHAR(64)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_route_stops
                DROP CONSTRAINT IF EXISTS delivery_route_stops_route_id_customer_id_key
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_route_stops
                DROP CONSTRAINT IF EXISTS uq_route_customer
                """
            )
        )
        conn.execute(text("DROP INDEX IF EXISTS uq_route_customer_so"))
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_route_customer_so
                ON delivery_route_stops (route_id, customer_id, COALESCE(description, ''))
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ADD COLUMN IF NOT EXISTS finance_paid_at TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ADD COLUMN IF NOT EXISTS finance_paid_by BIGINT
                REFERENCES users(id) ON DELETE SET NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS delivery_route_stop_lines (
                  id BIGSERIAL PRIMARY KEY,
                  stop_id BIGINT NOT NULL REFERENCES delivery_route_stops(id) ON DELETE CASCADE,
                  item_name TEXT NOT NULL,
                  quantity NUMERIC(12,3) NOT NULL,
                  sort_order INT NOT NULL DEFAULT 0,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_route_stop_lines_stop
                ON delivery_route_stop_lines(stop_id)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_routes
                ADD COLUMN IF NOT EXISTS vehicle_type_id BIGINT
                REFERENCES vehicle_types(id) ON UPDATE CASCADE
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE delivery_routes dr
                SET vehicle_type_id = v.type_id
                FROM vehicles v
                WHERE dr.vehicle_id = v.id
                  AND dr.vehicle_type_id IS NULL
                  AND v.type_id IS NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE delivery_routes dr
                SET vehicle_type_id = (
                  SELECT id FROM vehicle_types ORDER BY id LIMIT 1
                )
                WHERE dr.vehicle_type_id IS NULL
                  AND EXISTS (SELECT 1 FROM vehicle_types)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_routes
                ALTER COLUMN vehicle_id DROP NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_routes_vehicle_type
                ON delivery_routes(vehicle_type_id)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE delivery_routes
                ALTER COLUMN driver_id DROP NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ALTER COLUMN driver_id DROP NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ALTER COLUMN vehicle_id DROP NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE role_menu_access
                SET access_level = 'read'
                WHERE role = 'finance'
                  AND menu_id IN ('vehicle_types', 'warehouse')
                  AND access_level = 'none'
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ADD COLUMN IF NOT EXISTS delivery_route_id BIGINT
                REFERENCES delivery_routes(id) ON DELETE SET NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_delivery_route_id
                ON sales(delivery_route_id)
                WHERE delivery_route_id IS NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                DROP CONSTRAINT IF EXISTS sales_delivery_route_id_fkey
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE sales
                ADD CONSTRAINT sales_delivery_route_id_fkey
                FOREIGN KEY (delivery_route_id) REFERENCES delivery_routes(id)
                ON DELETE CASCADE
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id BIGSERIAL PRIMARY KEY,
                  username TEXT NOT NULL UNIQUE,
                  full_name TEXT NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT NOT NULL DEFAULT 'marketing',
                  is_active BOOLEAN NOT NULL DEFAULT TRUE,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_menus (
                  id TEXT PRIMARY KEY,
                  label TEXT NOT NULL,
                  path TEXT NOT NULL,
                  section TEXT NOT NULL,
                  icon TEXT NOT NULL,
                  sort_order INT NOT NULL DEFAULT 0,
                  read_permission TEXT NOT NULL,
                  write_permission TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS role_menu_access (
                  menu_id TEXT NOT NULL REFERENCES app_menus(id) ON DELETE CASCADE,
                  role TEXT NOT NULL,
                  access_level TEXT NOT NULL CHECK (access_level IN ('full', 'read', 'none')),
                  PRIMARY KEY (menu_id, role)
                )
                """
            )
        )

        conn.execute(
            text(
                """
                ALTER TABLE delivery_routes
                ADD COLUMN IF NOT EXISTS ritpiase INT NOT NULL DEFAULT 1
                """
            )
        )

        conn.execute(
            text(
                """
                ALTER TABLE drivers
                ADD COLUMN IF NOT EXISTS bank_name TEXT,
                ADD COLUMN IF NOT EXISTS bank_account TEXT
                """
            )
        )

        # --- Migrasi Master Uang Mel ---
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS uang_mel_master (
                  id BIGSERIAL PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  amount NUMERIC(14,2) NOT NULL DEFAULT 0,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )

        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'vehicle_types' AND column_name = 'uang_mel_id'
                  ) THEN
                    ALTER TABLE vehicle_types
                    ADD COLUMN uang_mel_id BIGINT REFERENCES uang_mel_master(id) ON DELETE SET NULL;
                  END IF;
                END $$;
                """
            )
        )
        # Drop kolom uang_mel lama dari vehicle_types (diganti relationship via uang_mel_id)
        conn.execute(
            text(
                """
                ALTER TABLE vehicle_types
                DROP COLUMN IF EXISTS uang_mel
                """
            )
        )

        # --- Customer lock & custom toll breakdown columns ---
        conn.execute(
            text(
                """
                ALTER TABLE customers
                ADD COLUMN IF NOT EXISTS custom_toll_breakdown TEXT
                """
            )
        )
        conn.execute(
            text(
                """
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
                      -- Both exist: drop the old one (leftover)
                      ALTER TABLE customers DROP COLUMN is_locked;
                    ELSE
                      -- Only is_locked exists: rename to is_locked_marketing
                      ALTER TABLE customers RENAME COLUMN is_locked TO is_locked_marketing;
                    END IF;
                  END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE customers
                ADD COLUMN IF NOT EXISTS is_locked_marketing BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS is_locked_finance BOOLEAN DEFAULT FALSE
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE customers
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'customers' AND column_name = 'updated_by_id'
                  ) THEN
                    ALTER TABLE customers
                    ADD COLUMN updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
                  END IF;
                END $$;
                """
            )
        )

        # --- App Settings table & finance_can_unlock_customer ---
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                  id BIGSERIAL PRIMARY KEY,
                  app_name TEXT NOT NULL DEFAULT 'Biaya Pengiriman',
                  app_subtitle TEXT NOT NULL DEFAULT 'Premium Logistics',
                  logo_base64 TEXT,
                  favicon_base64 TEXT,
                  finance_can_unlock_customer BOOLEAN NOT NULL DEFAULT FALSE,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE app_settings
                ADD COLUMN IF NOT EXISTS finance_can_unlock_customer BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
        )

        # Reset ALL sequences that may be out of sync after data import/restore
        conn.execute(
            text(
                """
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN
                        SELECT
                            t.relname AS table_name,
                            a.attname AS column_name,
                            pg_get_serial_sequence(t.relname::text, a.attname::text) AS seq_name
                        FROM pg_class t
                        JOIN pg_attribute a ON a.attrelid = t.oid
                        JOIN pg_namespace n ON n.oid = t.relnamespace
                        WHERE n.nspname = 'public'
                          AND t.relkind = 'r'
                          AND a.attnum > 0
                          AND NOT a.attisdropped
                          AND pg_get_serial_sequence(t.relname::text, a.attname::text) IS NOT NULL
                    LOOP
                        EXECUTE format(
                            'SELECT setval(%L, COALESCE((SELECT MAX(%I) FROM %I), 0) + 1, false)',
                            r.seq_name, r.column_name, r.table_name
                        );
                    END LOOP;
                END $$;
                """
            )
        )

    _seed_default_users()
    _seed_access_permissions()


def _seed_access_permissions() -> None:
    with SessionLocal() as db:
        from app.permissions_service import (
            reload_permissions_cache,
            seed_menus_and_access,
            sync_menu_definitions,
            sync_role_access,
        )

        seed_menus_and_access(db)
        sync_menu_definitions(db)
        sync_role_access(db)
        reload_permissions_cache(db)


def _seed_default_users() -> None:
    """Buat user admin default jika belum ada user."""
    with SessionLocal() as db:
        count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if count and int(count) > 0:
            return
        username = settings.admin_username.strip().lower()
        password_hash = hash_password(settings.admin_password)
        db.execute(
            text(
                """
                INSERT INTO users (username, full_name, password_hash, role, is_active)
                VALUES (:username, :full_name, :password_hash, 'admin', TRUE)
                """
            ),
            {
                "username": username,
                "full_name": "Administrator",
                "password_hash": password_hash,
            },
        )
        db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

