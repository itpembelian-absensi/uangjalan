-- ============================================================
-- Seed: Tol Bocimi (Ciawi–Cibadak / Parungkuda)
-- Seksi 1–2; Seksi 3 ke Sukabumi belum beroperasi
-- Tarif: Kepmen PUPR 1661/KPTS/M/2024 + acuan Seksi 1
-- ============================================================

-- Ciawi → Cigombong
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jawa Barat', 'Bocimi', 'Ciawi', 'Cigombong', 39, 28000, 37500, 106, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE name='Bocimi' AND origin_name='Ciawi' AND destination_name='Cigombong'
);

-- Ciawi → Parungkuda (Cibadak)
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jawa Barat', 'Bocimi', 'Ciawi', 'Parungkuda (Cibadak)', 39, 53000, 71000, 107, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE name='Bocimi' AND origin_name='Ciawi' AND destination_name='Parungkuda (Cibadak)'
);

-- Caringin → Cigombong
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jawa Barat', 'Bocimi', 'Caringin', 'Cigombong', 39, 28000, 37500, 108, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE name='Bocimi' AND origin_name='Caringin' AND destination_name='Cigombong'
);

-- Caringin → Parungkuda (Cibadak)
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jawa Barat', 'Bocimi', 'Caringin', 'Parungkuda (Cibadak)', 39, 53000, 71000, 109, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE name='Bocimi' AND origin_name='Caringin' AND destination_name='Parungkuda (Cibadak)'
);

-- Cigombong → Parungkuda (Cibadak)
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jawa Barat', 'Bocimi', 'Cigombong', 'Parungkuda (Cibadak)', 39, 25000, 33500, 110, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE name='Bocimi' AND origin_name='Cigombong' AND destination_name='Parungkuda (Cibadak)'
);

UPDATE toll_sections SET
  network = 'Jawa Barat',
  length_km = 39,
  is_active = true,
  gol23 = CASE destination_name
    WHEN 'Cigombong' THEN 28000
    WHEN 'Parungkuda (Cibadak)' THEN CASE origin_name WHEN 'Cigombong' THEN 25000 ELSE 53000 END
    ELSE gol23 END,
  gol45 = CASE destination_name
    WHEN 'Cigombong' THEN 37500
    WHEN 'Parungkuda (Cibadak)' THEN CASE origin_name WHEN 'Cigombong' THEN 33500 ELSE 71000 END
    ELSE gol45 END,
  sort_order = CASE
    WHEN origin_name='Ciawi' AND destination_name='Cigombong' THEN 106
    WHEN origin_name='Ciawi' AND destination_name='Parungkuda (Cibadak)' THEN 107
    WHEN origin_name='Caringin' AND destination_name='Cigombong' THEN 108
    WHEN origin_name='Caringin' AND destination_name='Parungkuda (Cibadak)' THEN 109
    WHEN origin_name='Cigombong' AND destination_name='Parungkuda (Cibadak)' THEN 110
    ELSE sort_order END
WHERE name = 'Bocimi'
  AND (
    (origin_name='Ciawi' AND destination_name IN ('Cigombong','Parungkuda (Cibadak)'))
    OR (origin_name='Caringin' AND destination_name IN ('Cigombong','Parungkuda (Cibadak)'))
    OR (origin_name='Cigombong' AND destination_name='Parungkuda (Cibadak)')
  );

DO $$
DECLARE
  v_sec RECORD;
  v_gol RECORD;
  v_rate NUMERIC;
BEGIN
  FOR v_sec IN
    SELECT id, origin_name, destination_name
    FROM toll_sections
    WHERE name = 'Bocimi'
      AND (
        (origin_name='Ciawi' AND destination_name IN ('Cigombong','Parungkuda (Cibadak)'))
        OR (origin_name='Caringin' AND destination_name IN ('Cigombong','Parungkuda (Cibadak)'))
        OR (origin_name='Cigombong' AND destination_name='Parungkuda (Cibadak)')
      )
  LOOP
    FOR v_gol IN SELECT id, code FROM toll_golongan WHERE code IN ('I','II','III','IV','V') LOOP
      IF v_sec.destination_name = 'Cigombong' THEN
        v_rate := CASE v_gol.code WHEN 'I' THEN 19000 WHEN 'II' THEN 28000 WHEN 'III' THEN 28000 WHEN 'IV' THEN 37500 WHEN 'V' THEN 37500 END;
      ELSIF v_sec.origin_name = 'Cigombong' AND v_sec.destination_name = 'Parungkuda (Cibadak)' THEN
        v_rate := CASE v_gol.code WHEN 'I' THEN 17000 WHEN 'II' THEN 25000 WHEN 'III' THEN 25000 WHEN 'IV' THEN 33500 WHEN 'V' THEN 33500 END;
      ELSE
        -- Ciawi/Caringin → Parungkuda (Cibadak) = seksi 1+2
        v_rate := CASE v_gol.code WHEN 'I' THEN 36000 WHEN 'II' THEN 53000 WHEN 'III' THEN 53000 WHEN 'IV' THEN 71000 WHEN 'V' THEN 71000 END;
      END IF;

      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec.id, v_gol.id, v_rate)
      ON CONFLICT (section_id, golongan_id) DO UPDATE SET rate = EXCLUDED.rate;
    END LOOP;
  END LOOP;
END $$;
