-- Rute pengiriman (sumber data) + relasi ke transaksi uang jalan
-- Jalankan di pgAdmin jika tidak memakai auto-migrasi ensure_schema()

BEGIN;

CREATE TABLE IF NOT EXISTS delivery_routes (
  id BIGSERIAL PRIMARY KEY,
  route_no TEXT NOT NULL UNIQUE,
  date DATE NOT NULL,
  vehicle_id BIGINT NOT NULL REFERENCES vehicles(id) ON UPDATE CASCADE,
  driver_id BIGINT NOT NULL REFERENCES drivers(id) ON UPDATE CASCADE,
  remarks TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_delivery_routes_date ON delivery_routes(date);
CREATE INDEX IF NOT EXISTS idx_delivery_routes_vehicle ON delivery_routes(vehicle_id);

CREATE TABLE IF NOT EXISTS delivery_route_stops (
  id BIGSERIAL PRIMARY KEY,
  route_id BIGINT NOT NULL REFERENCES delivery_routes(id) ON DELETE CASCADE,
  customer_id BIGINT NOT NULL REFERENCES customers(id) ON UPDATE CASCADE,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(route_id, customer_id)
);

CREATE INDEX IF NOT EXISTS idx_delivery_route_stops_route ON delivery_route_stops(route_id);

ALTER TABLE sales
  ADD COLUMN IF NOT EXISTS delivery_route_id BIGINT
  REFERENCES delivery_routes(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_delivery_route_id
  ON sales(delivery_route_id)
  WHERE delivery_route_id IS NOT NULL;

COMMIT;
