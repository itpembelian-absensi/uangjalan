-- ============================================================
-- Seed: Gerbang keluar Karawaci & Bitung (koridor Tangerang-Merak)
-- Sifat: Idempotent (aman dijalankan berulang)
-- Tarif = tarif resmi integrasi Jakarta–Tangerang / Tomang–Cikupa
-- (Kepmen PUPR 2692/KPTS/M/2024, berlaku 19 Okt 2024)
-- ============================================================

-- Karawaci
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Tangerang - Merak', 'Jakarta (Dalam Kota)', 'Karawaci', 98, 12500, 16500, 37, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'Tangerang - Merak'
    AND origin_name = 'Jakarta (Dalam Kota)'
    AND destination_name = 'Karawaci'
);

-- Bitung
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Tangerang - Merak', 'Jakarta (Dalam Kota)', 'Bitung', 98, 12500, 16500, 38, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'Tangerang - Merak'
    AND origin_name = 'Jakarta (Dalam Kota)'
    AND destination_name = 'Bitung'
);

-- Pastikan legacy gol23/gol45 ikut terbarui jika baris sudah ada
UPDATE toll_sections
SET gol23 = 12500, gol45 = 16500, sort_order = CASE destination_name WHEN 'Karawaci' THEN 37 WHEN 'Bitung' THEN 38 ELSE sort_order END, is_active = true
WHERE name = 'Tangerang - Merak'
  AND origin_name = 'Jakarta (Dalam Kota)'
  AND destination_name IN ('Karawaci', 'Bitung');

-- Tarif per golongan (I–V) untuk Karawaci & Bitung
DO $$
DECLARE
  v_sec RECORD;
  v_gol RECORD;
  v_rate NUMERIC;
BEGIN
  FOR v_sec IN
    SELECT id, destination_name
    FROM toll_sections
    WHERE name = 'Tangerang - Merak'
      AND origin_name = 'Jakarta (Dalam Kota)'
      AND destination_name IN ('Karawaci', 'Bitung')
  LOOP
    FOR v_gol IN SELECT id, code FROM toll_golongan WHERE code IN ('I', 'II', 'III', 'IV', 'V') LOOP
      v_rate := CASE v_gol.code
        WHEN 'I' THEN 8500
        WHEN 'II' THEN 12500
        WHEN 'III' THEN 12500
        WHEN 'IV' THEN 16500
        WHEN 'V' THEN 16500
      END;
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec.id, v_gol.id, v_rate)
      ON CONFLICT (section_id, golongan_id) DO UPDATE SET rate = EXCLUDED.rate;
    END LOOP;
  END LOOP;
END $$;
