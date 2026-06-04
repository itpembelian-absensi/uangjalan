-- Tambah jenis kendaraan per baris detail penjualan
-- Jalankan di pgAdmin (database uang_pengiriman)

ALTER TABLE sale_details
  ADD COLUMN IF NOT EXISTS vehicle_type_id BIGINT REFERENCES vehicle_types(id) ON UPDATE CASCADE;
