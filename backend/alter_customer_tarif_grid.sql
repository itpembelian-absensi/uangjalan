-- Grid tarif per customer: jenis kendaraan + uang jalan + tambahan
-- Jalankan di pgAdmin (database uang_pengiriman)

CREATE TABLE IF NOT EXISTS customer_vehicle_tariffs (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  vehicle_type_id BIGINT NOT NULL REFERENCES vehicle_types(id) ON DELETE CASCADE,
  uang_jalan NUMERIC(14,2) NOT NULL DEFAULT 0,
  tambahan_uang_jalan NUMERIC(14,2) NOT NULL DEFAULT 0,
  CONSTRAINT uq_customer_vehicle_type UNIQUE (customer_id, vehicle_type_id)
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'customers' AND column_name = 'vehicle_type_id'
  ) THEN
    INSERT INTO customer_vehicle_tariffs (customer_id, vehicle_type_id, uang_jalan, tambahan_uang_jalan)
    SELECT c.id, c.vehicle_type_id, COALESCE(c.uang_jalan, 0), 0
    FROM customers c
    WHERE c.vehicle_type_id IS NOT NULL
    ON CONFLICT (customer_id, vehicle_type_id) DO NOTHING;

    ALTER TABLE customers DROP COLUMN IF EXISTS vehicle_type_id;
    ALTER TABLE customers DROP COLUMN IF EXISTS uang_jalan;
  END IF;
END $$;
