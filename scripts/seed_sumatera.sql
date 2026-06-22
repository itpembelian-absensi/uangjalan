-- ============================================================
-- Seed: Ruas Tol Sumatera & Penyeberangan Ferry
-- Sifat: Idempotent (Aman dijalankan berulang tanpa merusak data lama)
-- ============================================================

-- 1. Penyeberangan Merak - Bakauheni
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Penyeberangan', 'Penyeberangan Merak - Bakauheni', 'Pelabuhan Merak', 'Pelabuhan Bakauheni', 30, 743800, 1225800, 0, true
WHERE NOT EXISTS (SELECT 1 FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni');

-- 2. Bakauheni - Terbanggi Besar
INSERT INTO toll_sections (network, name, origin_name, destination_name, length_km, gol23, gol45, sort_order, is_active)
SELECT 'Jalan Tol Trans-Sumatera', 'Bakauheni - Terbanggi Besar', 'Bakauheni', 'Terbanggi Besar', 140, 170000, 220000, 0, true
WHERE NOT EXISTS (SELECT 1 FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar');

-- 3. Tambahkan tarif per golongan (toll_section_rates) menggunakan ON CONFLICT DO NOTHING
-- Golongan I
DO $$
DECLARE
  v_gol_id INTEGER;
  v_sec_id INTEGER;
BEGIN
  SELECT id INTO v_gol_id FROM toll_golongan WHERE code = 'I' LIMIT 1;
  IF v_gol_id IS NOT NULL THEN
    -- Ferry Gol I
    SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni' LIMIT 1;
    IF v_sec_id IS NOT NULL THEN
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec_id, v_gol_id, 481800)
      ON CONFLICT (section_id, golongan_id) DO NOTHING;
    END IF;
    -- Bakauheni-Terbanggi Gol I
    SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar' LIMIT 1;
    IF v_sec_id IS NOT NULL THEN
      INSERT INTO toll_section_rates (section_id, golongan_id, rate)
      VALUES (v_sec_id, v_gol_id, 118500)
      ON CONFLICT (section_id, golongan_id) DO NOTHING;
    END IF;
  END IF;
END $$;

-- Golongan II & III
DO $$
DECLARE
  v_gol_id INTEGER;
  v_sec_id INTEGER;
  v_code TEXT;
BEGIN
  FOR v_code IN SELECT unnest(ARRAY['II','III']) LOOP
    SELECT id INTO v_gol_id FROM toll_golongan WHERE code = v_code LIMIT 1;
    IF v_gol_id IS NOT NULL THEN
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 743800)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 170000)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
    END IF;
  END LOOP;
END $$;

-- Golongan IV & V
DO $$
DECLARE
  v_gol_id INTEGER;
  v_sec_id INTEGER;
  v_code TEXT;
BEGIN
  FOR v_code IN SELECT unnest(ARRAY['IV','V']) LOOP
    SELECT id INTO v_gol_id FROM toll_golongan WHERE code = v_code LIMIT 1;
    IF v_gol_id IS NOT NULL THEN
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Penyeberangan Merak - Bakauheni' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 1225800)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
      SELECT id INTO v_sec_id FROM toll_sections WHERE name = 'Bakauheni - Terbanggi Besar' LIMIT 1;
      IF v_sec_id IS NOT NULL THEN
        INSERT INTO toll_section_rates (section_id, golongan_id, rate)
        VALUES (v_sec_id, v_gol_id, 220000)
        ON CONFLICT (section_id, golongan_id) DO NOTHING;
      END IF;
    END IF;
  END LOOP;
END $$;

-- ============================================================
-- Seed: Jenis Kendaraan FUSO 6 Roda Panjang (Golongan IV)
-- Sifat: Idempotent (Aman dijalankan berulang)
-- ============================================================
DO $$
DECLARE
  v_gol_iv_id INTEGER;
  v_bbm_id INTEGER;
  v_uang_mel_id INTEGER;
  v_km_per_liter NUMERIC;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM vehicle_types WHERE name = 'FUSO 6 Roda Panjang') THEN
    SELECT id INTO v_gol_iv_id FROM toll_golongan WHERE code = 'IV' LIMIT 1;
    -- Ambil referensi dari FUSO yang sudah ada untuk nilai default
    SELECT bbm_id, uang_mel_id, km_per_liter
      INTO v_bbm_id, v_uang_mel_id, v_km_per_liter
      FROM vehicle_types
      WHERE name ILIKE '%fuso%roda%'
      LIMIT 1;
    
    INSERT INTO vehicle_types (name, toll_golongan_id, bbm_id, uang_mel_id, km_per_liter)
    VALUES ('FUSO 6 Roda Panjang', v_gol_iv_id, v_bbm_id, v_uang_mel_id, v_km_per_liter);
  END IF;
END $$;
