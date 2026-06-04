# Uang Pengiriman (Kontrol & Pengeluaran Supir)

Aplikasi sederhana untuk mengelola:
- Master: customer, merek kendaraan, jenis kendaraan, plat mobil, supir
- Transaksi: pengeluaran uang jalan per customer

## 1) Database (PostgreSQL lokal)

1. Buat database:

```sql
CREATE DATABASE uang_pengiriman;
```

2. Jalankan schema:

```bash
psql -U postgres -d uang_pengiriman -f schema.sql
```

### Migrasi hapus surat jalan

Jalankan di pgAdmin: `backend/alter_remove_delivery_notes.sql`

Pengeluaran langsung ke `customer_id` (tanpa surat jalan).

### Migrasi tarif grid per customer

Jika database sudah ada sebelumnya, jalankan di pgAdmin:

`backend/alter_customer_tarif_grid.sql`

Membuat tabel `customer_vehicle_tariffs` (jenis + uang jalan + tambahan per partner).

## 2) Struktur data

- `customers` + `customer_vehicle_tariffs` (grid tarif per jenis kendaraan per partner)
- `vehicle_brands`
- `vehicle_types`
- `vehicles` (plat + relasi merek/jenis)
- `drivers`
- `cash_disbursements` (pengeluaran uang per customer + jenis kendaraan)

## Rute pengiriman → Uang jalan

Alur yang benar:

1. Buat **Rute Pengiriman** (tanggal, mobil, sopir, urutan customer) di menu **Rute Pengiriman**
2. Klik **Uang Jalan** pada rute → sistem membuat/memperbarui transaksi uang jalan dari tarif customer
3. Sesuaikan nominal tambahan di menu **Uang Jalan** (edit saja; tanpa rute tidak bisa tambah transaksi baru)

Migrasi database: otomatis saat `npm run dev`, atau jalankan `backend/alter_delivery_routes.sql` di pgAdmin.

## Berikutnya

Sudah tersedia:
- Backend API (FastAPI) untuk CRUD master + CRUD surat jalan + input pengeluaran
- UI web sederhana (server-side) untuk input master/surat jalan/pengeluaran

### Koneksi PostgreSQL (penting)

Edit `backend/.env` — sesuaikan **password PostgreSQL Anda** di `DATABASE_URL`:

```env
DATABASE_URL=postgresql+pg8000://postgres:PASSWORD_ANDA@localhost:5432/uang_pengiriman
```

Ganti `PASSWORD_ANDA` dengan password user `postgres` di pgAdmin (bukan `password` dari contoh, kecuali memang itu password Anda).

Setelah mengubah `.env`, **restart** `npm run dev`.

## Menjalankan aplikasi (satu perintah)

Dari folder root project:

```powershell
cd "d:\Programer\Uang Pengiriman"
npm install
npm run dev
```

Ini menjalankan **backend** (port 8001) dan **frontend React** (port 5173) sekaligus.

Buka di browser: **http://localhost:5173**

Backend API berjalan di port **8001** (bukan 8000), agar tidak bentrok dengan proses lama.

Hentikan server: `npm run stop` lalu jalankan lagi `npm run dev`.

### Server mati setelah update?

- **Satu terminal saja** untuk `npm run dev` — jangan tutup / Ctrl+C kecuali memang mau stop.
- Setelah file backend berubah (`.py`, `.env`), server **mati lalu nyala ulang otomatis** (~2,5 detik setelah edit selesai).
- Perubahan halaman React (`frontend/src`) tetap pakai **hot reload** Vite (tanpa restart penuh).
- Jika error database atau syntax Python, backend **coba nyala ulang** sendiri (maks. 10x).
- Tanpa auto-restart penuh: `npm run dev:fast`
- Jangan jalankan `npm run dev` di banyak terminal sekaligus (bentrok port).

| Perintah | Fungsi |
|----------|--------|
| `npm run dev` | Backend + frontend bersamaan |
| `npm run dev:backend` | Hanya API (port 8001) |
| `npm run dev:frontend` | Hanya UI React (port 5173) |

## UI lama (opsional)

UI HTML sederhana masih ada di backend:
- `http://127.0.0.1:8000/ui`
- Laporan: `http://127.0.0.1:8000/ui/reports` (filter tanggal, rekap supir/customer, detail SJ)

## Login & Role Akses

Aplikasi memakai login berbasis database dengan 3 role. Lihat **Matriks Akses** di menu Administrasi untuk detail per menu.

### Matriks akses per menu

| Menu | Admin | Finance & Accounting | Marketing |
|------|:-----:|:--------------------:|:---------:|
| Dashboard | Lihat & Edit | Lihat saja | Lihat saja |
| Customers | Lihat & Edit | Lihat saja | Lihat & Edit |
| Drivers | Lihat & Edit | Lihat saja | Lihat & Edit |
| Vehicles | Lihat & Edit | Lihat saja | Lihat & Edit |
| Merek | Lihat & Edit | — | Lihat & Edit |
| Jenis Kendaraan | Lihat & Edit | — | Lihat & Edit |
| Gudang | Lihat & Edit | — | Lihat & Edit |
| Master BBM | Lihat & Edit | — | Lihat & Edit |
| Golongan Tol | Lihat & Edit | — | Lihat & Edit |
| Ruas Tol | Lihat & Edit | — | Lihat & Edit |
| Rute Pengiriman | Lihat & Edit | Lihat saja | Lihat & Edit |
| Uang Jalan | Lihat & Edit | Lihat & Edit | — |
| Laporan | Lihat saja | Lihat saja | Lihat saja |
| Manajemen User | Lihat & Edit | — | — |
| Matriks Akses | Lihat saja | Lihat saja | Lihat saja |

**Keterangan:** *Lihat & Edit* = buka menu + tambah/ubah/hapus data · *Lihat saja* = buka menu, tanpa ubah data · *—* = menu tidak tampil

User default dibuat otomatis saat pertama kali jalan (jika belum ada user), dari `backend/.env`:
- `ADMIN_USERNAME` (default: admin)
- `ADMIN_PASSWORD` (default: admin)
- `SESSION_SECRET` (wajib diganti untuk keamanan)

Kelola user tambahan di menu **Manajemen User** (hanya Admin).

**Edit matriks akses:** Admin buka **Matriks Akses** → ubah dropdown per menu × role → tersimpan otomatis di database.

UI React: **http://localhost:5173/login**

UI lama (HTML) juga memakai login yang sama via session cookie.

API laporan:
- `GET /api/reports/by-driver?from=2026-05-01&to=2026-05-31`
- `GET /api/reports/by-customer?from=2026-05-01&to=2026-05-31`
- `GET /api/reports/delivery-details?from=2026-05-01&to=2026-05-31&driver_id=1`

## Data contoh (opsional)

```powershell
cd "d:\Programer\Uang Pengiriman\backend"
.\seed.ps1
```

## Fitur tambahan

- Detail surat jalan + tambah/hapus pengeluaran per SJ
- Filter tanggal di daftar surat jalan & pengeluaran
- Export laporan ke CSV
- Format nominal Rupiah di UI

