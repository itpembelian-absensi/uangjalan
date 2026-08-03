-- ============================================================
-- Seed: Kayu Besar → Bintaro (via Ulujami)
-- 1) JORR · Kayu Besar → Ulujami
-- 2) Pondok Aren-Bintaro Viaduct-Ulujami · Ulujami → Pondok Aren
-- Sifat: Idempotent
-- ============================================================

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jabodetabek', 'JORR', 'Kayu Besar', 'Ulujami', 18, 25000, 33500, 109, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'JORR' AND origin_name = 'Kayu Besar' AND destination_name = 'Ulujami'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jabodetabek', 'Pondok Aren-Bintaro Viaduct-Ulujami', 'Ulujami', 'Pondok Aren', 8.5, 25000, 33500, 110, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections
  WHERE name = 'Pondok Aren-Bintaro Viaduct-Ulujami'
    AND origin_name = 'Ulujami'
    AND destination_name = 'Pondok Aren'
);

UPDATE toll_sections
SET gol23 = 25000,
    gol45 = 33500,
    length_km = 18,
    network = 'Jabodetabek',
    is_active = true,
    sort_order = 109
WHERE name = 'JORR'
  AND origin_name = 'Kayu Besar'
  AND destination_name = 'Ulujami';

UPDATE toll_sections
SET gol23 = 25000,
    gol45 = 33500,
    length_km = 8.5,
    network = 'Jabodetabek',
    is_active = true,
    sort_order = 110
WHERE name = 'Pondok Aren-Bintaro Viaduct-Ulujami'
  AND origin_name = 'Ulujami'
  AND destination_name = 'Pondok Aren';

DO $$
DECLARE
  v_sec RECORD;
  v_gol RECORD;
  v_rate NUMERIC;
BEGIN
  FOR v_sec IN
    SELECT id, name, origin_name, destination_name
    FROM toll_sections
    WHERE (
      name = 'JORR' AND origin_name = 'Kayu Besar' AND destination_name = 'Ulujami'
    ) OR (
      name = 'Pondok Aren-Bintaro Viaduct-Ulujami'
      AND origin_name = 'Ulujami'
      AND destination_name = 'Pondok Aren'
    )
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
