-- Tarif uang jalan per jenis kendaraan + pengeluaran per jenis
-- Jalankan di pgAdmin (database uang_pengiriman)

ALTER TABLE vehicle_types ADD COLUMN IF NOT EXISTS uang_jalan NUMERIC(14,2) NOT NULL DEFAULT 0;

ALTER TABLE cash_disbursements ADD COLUMN IF NOT EXISTS vehicle_type_id BIGINT REFERENCES vehicle_types(id);

ALTER TABLE vehicles ALTER COLUMN type_id DROP NOT NULL;

-- Contoh tarif (sesuaikan jika sudah ada data dengan nama sama)
INSERT INTO vehicle_types (name, uang_jalan) VALUES
  ('Tronton', 100000),
  ('Fuso', 50000),
  ('Double', 30000),
  ('Engkel', 25000),
  ('Grand Max', 10000)
ON CONFLICT (name) DO UPDATE SET uang_jalan = EXCLUDED.uang_jalan;
