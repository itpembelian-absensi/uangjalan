-- ============================================================
-- Seed: JORR dari Kayu Besar → Jati Asih / Cikunir / Cilincing / Kebon Bawang (Priok)
-- Sifat: Idempotent
-- Tarif flat JORR + ATP (Kepmen PUPR 1604/KPTS/M/2023)
-- ============================================================

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jabodetabek', 'JORR', 'Kayu Besar', 'Jati Asih', 66, 25000, 33500, 102, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'JORR' AND origin_name = 'Kayu Besar' AND destination_name = 'Jati Asih'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jabodetabek', 'JORR', 'Kayu Besar', 'Cikunir', 66, 25000, 33500, 103, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'JORR' AND origin_name = 'Kayu Besar' AND destination_name = 'Cikunir'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jabodetabek', 'JORR', 'Kayu Besar', 'Cilincing', 66, 25000, 33500, 104, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'JORR' AND origin_name = 'Kayu Besar' AND destination_name = 'Cilincing'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jabodetabek', 'JORR', 'Kayu Besar', 'Kebon Bawang', 66, 25000, 33500, 105, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'JORR' AND origin_name = 'Kayu Besar' AND destination_name = 'Kebon Bawang'
);

UPDATE toll_sections
SET gol23 = 25000,
    gol45 = 33500,
    length_km = 66,
    network = 'Jabodetabek',
    is_active = true,
    sort_order = CASE destination_name
      WHEN 'Jati Asih' THEN 102
      WHEN 'Cikunir' THEN 103
      WHEN 'Cilincing' THEN 104
      WHEN 'Kebon Bawang' THEN 105
      ELSE sort_order
    END
WHERE name = 'JORR'
  AND origin_name = 'Kayu Besar'
  AND destination_name IN ('Jati Asih', 'Cikunir', 'Cilincing', 'Kebon Bawang');

DO $$
DECLARE
  v_sec RECORD;
  v_gol RECORD;
  v_rate NUMERIC;
BEGIN
  FOR v_sec IN
    SELECT id, destination_name
    FROM toll_sections
    WHERE name = 'JORR'
      AND origin_name = 'Kayu Besar'
      AND destination_name IN ('Jati Asih', 'Cikunir', 'Cilincing', 'Kebon Bawang')
  LOOP
    FOR v_gol IN SELECT id, code FROM toll_golongan WHERE code IN ('I', 'II', 'III', 'IV', 'V') LOOP
      v_rate := CASE v_gol.code
        WHEN 'I' THEN 17000
        WHEN 'II' THEN 25000
        WHEN 'III' THEN 25000
        WHEN 'IV' THEN 33500
        WHEN 'V' THEN 33500
      END;
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec.id, v_gol.id, v_rate)
      ON CONFLICT (section_id, golongan_id) DO UPDATE SET rate = EXCLUDED.rate;
    END LOOP;
  END LOOP;
END $$;
