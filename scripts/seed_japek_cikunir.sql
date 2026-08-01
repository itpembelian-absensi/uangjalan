-- ============================================================
-- Seed: Jakarta-Cikampek dari Cikunir → Bekasi/Cikarang/Karawang/Cikampek
-- Tarif: selisih zona dari Kepmen 250/KPTS/M/2024 (Jakarta IC matrix)
-- ============================================================

-- Helper pattern: insert section if missing, then rates via Python upsert on deploy.
-- SQL seed ensures rows exist even before Python runs.

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Bekasi Barat', 'Cikunir', 'Bekasi Barat', 73, 6000, 8000, 280, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Bekasi Barat' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Bekasi Timur', 'Cikunir', 'Bekasi Timur', 73, 6000, 8000, 281, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Bekasi Timur' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Tambun', 'Cikunir', 'Tambun', 73, 6000, 8000, 282, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Tambun' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Cibitung', 'Cikunir', 'Cibitung', 73, 6000, 8000, 283, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Cibitung' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Cikarang Barat', 'Cikunir', 'Cikarang Barat', 73, 6000, 8000, 284, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Cikarang Barat' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Cibatu', 'Cikunir', 'Cibatu', 73, 10500, 13500, 285, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Cibatu' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Cikarang Timur', 'Cikunir', 'Cikarang Timur', 73, 10500, 13500, 286, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Cikarang Timur' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Karawang Barat', 'Cikunir', 'Karawang Barat', 73, 10500, 13500, 287, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Karawang Barat' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Karawang Timur', 'Cikunir', 'Karawang Timur', 73, 26500, 35000, 288, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Karawang Timur' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Dawuan', 'Cikunir', 'Dawuan', 73, 26500, 35000, 289, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Dawuan' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Kalihurip', 'Cikunir', 'Kalihurip', 73, 26500, 35000, 290, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Kalihurip' AND name ILIKE '%Cikampek%'
);

INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Trans Jawa', 'Jakarta-Cikampek · Cikunir → Cikampek', 'Cikunir', 'Cikampek', 73, 26500, 35000, 291, true
WHERE NOT EXISTS (
  SELECT 1 FROM toll_sections WHERE origin_name='Cikunir' AND destination_name='Cikampek' AND name ILIKE '%Cikampek%'
);

-- Align names / sort / gol columns
UPDATE toll_sections SET
  network = 'Trans Jawa',
  name = 'Jakarta-Cikampek · Cikunir → ' || destination_name,
  length_km = 73,
  is_active = true,
  sort_order = CASE destination_name
    WHEN 'Bekasi Barat' THEN 280
    WHEN 'Bekasi Timur' THEN 281
    WHEN 'Tambun' THEN 282
    WHEN 'Cibitung' THEN 283
    WHEN 'Cikarang Barat' THEN 284
    WHEN 'Cibatu' THEN 285
    WHEN 'Cikarang Timur' THEN 286
    WHEN 'Karawang Barat' THEN 287
    WHEN 'Karawang Timur' THEN 288
    WHEN 'Dawuan' THEN 289
    WHEN 'Kalihurip' THEN 290
    WHEN 'Cikampek' THEN 291
    ELSE sort_order
  END,
  gol23 = CASE destination_name
    WHEN 'Bekasi Barat' THEN 6000
    WHEN 'Bekasi Timur' THEN 6000
    WHEN 'Tambun' THEN 6000
    WHEN 'Cibitung' THEN 6000
    WHEN 'Cikarang Barat' THEN 6000
    WHEN 'Cibatu' THEN 10500
    WHEN 'Cikarang Timur' THEN 10500
    WHEN 'Karawang Barat' THEN 10500
    ELSE 26500
  END,
  gol45 = CASE destination_name
    WHEN 'Bekasi Barat' THEN 8000
    WHEN 'Bekasi Timur' THEN 8000
    WHEN 'Tambun' THEN 8000
    WHEN 'Cibitung' THEN 8000
    WHEN 'Cikarang Barat' THEN 8000
    WHEN 'Cibatu' THEN 13500
    WHEN 'Cikarang Timur' THEN 13500
    WHEN 'Karawang Barat' THEN 13500
    ELSE 35000
  END
WHERE origin_name = 'Cikunir'
  AND name ILIKE '%Cikampek%'
  AND destination_name IN (
    'Bekasi Barat','Bekasi Timur','Tambun','Cibitung','Cikarang Barat',
    'Cibatu','Cikarang Timur','Karawang Barat','Karawang Timur',
    'Dawuan','Kalihurip','Cikampek'
  );
