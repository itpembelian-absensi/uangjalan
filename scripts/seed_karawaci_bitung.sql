-- ============================================================
-- Seed: Gerbang keluar Karawaci & Bitung (koridor Tangerang-Merak)
-- Sifat: Idempotent (aman dijalankan berulang)
-- Tarif = sama dengan Cikupa (segmen integrasi Tomang–Cikupa)
-- ============================================================

-- Karawaci
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Tangerang - Merak', 'Jakarta (Dalam Kota)', 'Karawaci', 98, 28500, 38000, 37, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'Tangerang - Merak'
    AND origin_name = 'Jakarta (Dalam Kota)'
    AND destination_name = 'Karawaci'
);

-- Bitung
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Tangerang - Merak', 'Jakarta (Dalam Kota)', 'Bitung', 98, 28500, 38000, 38, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'Tangerang - Merak'
    AND origin_name = 'Jakarta (Dalam Kota)'
    AND destination_name = 'Bitung'
);

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
        WHEN 'I' THEN 19000
        WHEN 'II' THEN 28500
        WHEN 'III' THEN 28500
        WHEN 'IV' THEN 38000
        WHEN 'V' THEN 38000
      END;
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec.id, v_gol.id, v_rate)
      ON CONFLICT (section_id, golongan_id) DO NOTHING;
    END LOOP;
  END LOOP;
END $$;
