-- Hapus surat jalan: pengeluaran langsung ke customer
-- Jalankan di pgAdmin (database uang_pengiriman)

ALTER TABLE cash_disbursements ADD COLUMN IF NOT EXISTS customer_id BIGINT REFERENCES customers(id);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'cash_disbursements'
      AND column_name = 'delivery_note_id'
  ) THEN
    UPDATE cash_disbursements cd
    SET customer_id = dn.customer_id
    FROM delivery_notes dn
    WHERE cd.delivery_note_id = dn.id AND cd.customer_id IS NULL;

    ALTER TABLE cash_disbursements DROP CONSTRAINT IF EXISTS cash_disbursements_delivery_note_id_fkey;
    ALTER TABLE cash_disbursements DROP COLUMN delivery_note_id;
  END IF;
END $$;

ALTER TABLE cash_disbursements ALTER COLUMN customer_id SET NOT NULL;

DROP TABLE IF EXISTS delivery_notes CASCADE;
