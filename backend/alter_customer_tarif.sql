-- Tarif uang jalan & jenis kendaraan per customer (partner)
-- Jalankan di pgAdmin (database uang_pengiriman)

ALTER TABLE customers ADD COLUMN IF NOT EXISTS vehicle_type_id BIGINT REFERENCES vehicle_types(id) ON DELETE SET NULL;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS uang_jalan NUMERIC(14,2) NOT NULL DEFAULT 0;

-- Opsional: salin tarif lama dari vehicle_types ke customer yang sudah punya jenis
-- UPDATE customers c
-- SET uang_jalan = vt.uang_jalan
-- FROM vehicle_types vt
-- WHERE c.vehicle_type_id = vt.id AND c.uang_jalan = 0;
