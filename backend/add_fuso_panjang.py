import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import VehicleType, TollGolongan, BbmMaster, UangMelMaster

def main():
    db = SessionLocal()
    try:
        # Cek apakah sudah ada
        existing = db.query(VehicleType).filter_by(name="FUSO 6 Roda Panjang").first()
        if existing:
            print("Jenis kendaraan 'FUSO 6 Roda Panjang' sudah ada.")
            return

        # Cari FUSO 4 Roda / FUSO 6 Roda yang sudah ada sebagai referensi
        fuso_existing = db.query(VehicleType).filter(
            VehicleType.name.ilike("%fuso%roda%")
        ).first()

        # Cari Golongan IV (untuk truk panjang 7-10 meter)
        gol_iv = db.query(TollGolongan).filter_by(code="IV").first()
        if not gol_iv:
            print("Golongan IV tidak ditemukan!")
            return

        # Ambil BBM dan Uang Mel dari FUSO yang sudah ada, jika ada
        bbm_id = fuso_existing.bbm_id if fuso_existing else None
        uang_mel_id = fuso_existing.uang_mel_id if fuso_existing else None
        km_per_liter = fuso_existing.km_per_liter if fuso_existing else None

        new_vt = VehicleType(
            name="FUSO 6 Roda Panjang",
            toll_golongan_id=gol_iv.id,
            bbm_id=bbm_id,
            uang_mel_id=uang_mel_id,
            km_per_liter=km_per_liter,
        )
        db.add(new_vt)
        db.commit()

        print(f"Berhasil menambahkan jenis kendaraan: FUSO 6 Roda Panjang")
        print(f"  - Golongan Tol: {gol_iv.code} ({gol_iv.name})")
        print(f"  - BBM ID: {bbm_id}")
        print(f"  - Uang Mel ID: {uang_mel_id}")
        print(f"  - KM/Liter: {km_per_liter}")

        if fuso_existing:
            print(f"  (Referensi dari: {fuso_existing.name})")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
