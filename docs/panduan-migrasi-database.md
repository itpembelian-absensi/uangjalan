# Panduan Migrasi Skema Database

## Ringkasan

Project ini menggunakan **auto-migration** via fungsi `ensure_schema()` di `backend/app/db.py`. Setiap kali backend container start, fungsi ini dijalankan dan akan menerapkan semua perubahan skema secara otomatis dan idempotent (aman dijalankan berulang).

**Tidak perlu** menjalankan migrasi manual di server. Cukup push ke `main`, CI/CD akan deploy dan backend otomatis apply migrasi saat restart.

---

## Alur Deploy & Migrasi

```
Push ke main
    │
    ▼
CI/CD (GitHub Actions, self-hosted runner)
    │
    ├── 1. git pull kode terbaru
    ├── 2. npm build frontend
    ├── 3. run_migrations (via psql ke container db) ← safety net
    ├── 4. docker compose up (restart semua container)
    │       └── backend start → ensure_schema() ← migrasi utama
    └── 5. health check
```

Ada **dua lapis** migrasi:
1. **`scripts/deploy.sh` → `run_migrations()`** — SQL langsung via psql (safety net, jalan sebelum app start)
2. **`backend/app/db.py` → `ensure_schema()`** — Python/SQLAlchemy (migrasi utama, jalan saat app boot)

---

## Cara Menambah Kolom Baru

### Langkah 1: Update Model SQLAlchemy

Edit `backend/app/models.py`, tambahkan kolom baru:

```python
class Customer(Base):
    __tablename__ = "customers"
    # ... kolom existing ...
    kolom_baru: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Langkah 2: Tambahkan Migrasi di `ensure_schema()`

Edit `backend/app/db.py`, tambahkan statement **sebelum** block "Reset ALL sequences":

```python
        # --- Deskripsi singkat perubahan ---
        conn.execute(
            text(
                """
                ALTER TABLE nama_tabel
                ADD COLUMN IF NOT EXISTS kolom_baru TEXT
                """
            )
        )
```

### Langkah 3: (Opsional) Tambahkan ke `deploy.sh`

Jika ingin migrasi jalan lebih awal (sebelum app start), tambahkan juga di `scripts/deploy.sh` di dalam fungsi `run_migrations()`:

```sql
ALTER TABLE nama_tabel ADD COLUMN IF NOT EXISTS kolom_baru TEXT;
```

### Langkah 4: Update Schema Pydantic

Jika kolom dipakai di API, update `backend/app/schemas.py`:

```python
class CustomerOut(BaseModel):
    kolom_baru: str | None = None
```

### Langkah 5: Push ke main

```bash
git add backend/app/models.py backend/app/db.py backend/app/schemas.py
git commit -m "feat: add kolom_baru to customers table"
git push origin main
```

CI/CD akan otomatis deploy dan migrasi berjalan.

---

## Aturan Penting

### ✅ WAJIB

| # | Aturan |
|---|--------|
| 1 | Selalu gunakan `IF NOT EXISTS` atau `ADD COLUMN IF NOT EXISTS` |
| 2 | Selalu tambahkan default value untuk kolom NOT NULL |
| 3 | Untuk FK dengan `REFERENCES`, gunakan pattern DO $$ ... IF NOT EXISTS |
| 4 | Test lokal dulu sebelum push |
| 5 | Pastikan model di `models.py` sinkron dengan migrasi di `db.py` |

### ❌ JANGAN

| # | Larangan |
|---|----------|
| 1 | Jangan DROP COLUMN di production tanpa koordinasi |
| 2 | Jangan RENAME COLUMN (tambah kolom baru, copy data, hapus yang lama) |
| 3 | Jangan ALTER COLUMN type secara langsung jika ada data |
| 4 | Jangan buat migrasi yang tidak idempotent |

---

## Pattern untuk Berbagai Kasus

### Tambah Kolom Biasa

```python
conn.execute(text("""
    ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS nama_kolom TEXT
"""))
```

### Tambah Kolom NOT NULL dengan Default

```python
conn.execute(text("""
    ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE
"""))
```

### Tambah Kolom dengan Foreign Key

```python
conn.execute(text("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'customers' AND column_name = 'category_id'
      ) THEN
        ALTER TABLE customers
        ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL;
      END IF;
    END $$;
"""))
```

> **Kenapa pakai DO $$ untuk FK?** Karena `ADD COLUMN IF NOT EXISTS` tidak support `REFERENCES` clause di beberapa versi PostgreSQL. Pattern DO $$ lebih aman.

### Buat Tabel Baru

```python
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS nama_tabel (
      id BIGSERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""))
```

### Tambah Index

```python
conn.execute(text("""
    CREATE INDEX IF NOT EXISTS idx_customers_city
    ON customers(city)
"""))
```

### Tambah Unique Constraint

```python
conn.execute(text("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_nama_constraint
    ON nama_tabel(kolom1, kolom2)
"""))
```

---

## Testing Lokal

Sebelum push, pastikan:

1. **Restart backend lokal** — pastikan `ensure_schema()` jalan tanpa error:
   ```powershell
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Cek kolom sudah ada** di database:
   ```sql
   SELECT column_name, data_type, is_nullable
   FROM information_schema.columns
   WHERE table_name = 'customers'
   ORDER BY ordinal_position;
   ```

3. **Test API endpoint** yang pakai kolom baru.

---

## Troubleshooting

### App error setelah deploy

**Gejala:** "Koneksi atau query database gagal"

**Penyebab:** Model SQLAlchemy mengharapkan kolom yang belum ada di database.

**Solusi:** Pastikan migrasi `ALTER TABLE ADD COLUMN IF NOT EXISTS` sudah ada di `ensure_schema()`.

### Migrasi gagal di CI/CD

**Gejala:** Deploy script error di step `run_migrations`

**Penyebab:** Container db belum ready saat psql dijalankan.

**Solusi:** Script sudah handle ini dengan `pg_isready` loop. Jika tetap gagal, migrasi akan tetap jalan via `ensure_schema()` saat backend start.

### Kolom sudah ada tapi error tetap muncul

**Penyebab:** Kemungkinan tipe data tidak cocok antara model dan database.

**Solusi:** Cek tipe di model (`models.py`) vs tipe di database. Gunakan `ALTER COLUMN ... TYPE` dengan hati-hati.

---

## Struktur File Terkait

```
backend/
├── app/
│   ├── db.py          ← ensure_schema() - migrasi utama
│   ├── models.py      ← definisi tabel SQLAlchemy
│   └── schemas.py     ← Pydantic schemas untuk API
├── migrate_*.py       ← script migrasi standalone (opsional, untuk dev lokal)
scripts/
└── deploy.sh          ← deploy script dengan run_migrations()
```
