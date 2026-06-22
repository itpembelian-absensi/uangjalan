import sys
import os

# Menambahkan path backend ke sys.path agar bisa import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollSection, TollGolongan, TollSectionRate

def main():
    db = SessionLocal()
    try:
        # Pastikan golongan tol sudah ada, atau ambil jika ada
        gol_II = db.query(TollGolongan).filter_by(code="II").first()
        gol_III = db.query(TollGolongan).filter_by(code="III").first()
        gol_IV = db.query(TollGolongan).filter_by(code="IV").first()
        gol_V = db.query(TollGolongan).filter_by(code="V").first()

        if not gol_II:
            print("Golongan II belum ada, pastikan master golongan tol sudah diisi.")
            return

        sections_to_add = [
            {
                "network": "Penyeberangan",
                "name": "Penyeberangan Merak - Bakauheni",
                "origin_name": "Pelabuhan Merak",
                "destination_name": "Pelabuhan Bakauheni",
                "length_km": 30, # estimasi
                "rates": {
                    gol_II: 743800, # estimasi Gol V Penumpang / Gol IV Barang (truk sedang)
                    gol_III: 743800, 
                    gol_IV: 1225800,
                    gol_V: 1225800
                }
            },
            {
                "network": "Jalan Tol Trans-Jawa",
                "name": "Tangerang - Merak",
                "origin_name": "Tangerang",
                "destination_name": "Merak",
                "length_km": 73,
                "rates": {
                    gol_II: 80000,
                    gol_III: 80000,
                    gol_IV: 105000,
                    gol_V: 105000
                }
            },
            {
                "network": "Jalan Tol Trans-Sumatera",
                "name": "Bakauheni - Terbanggi Besar",
                "origin_name": "Bakauheni",
                "destination_name": "Terbanggi Besar",
                "length_km": 140,
                "rates": {
                    gol_II: 170000,
                    gol_III: 170000,
                    gol_IV: 220000,
                    gol_V: 220000
                }
            }
        ]

        added_count = 0
        for sec_data in sections_to_add:
            existing = db.query(TollSection).filter_by(name=sec_data["name"]).first()
            if not existing:
                rates_data = sec_data.pop("rates")
                # set gol23 and gol45 fallback values
                sec_data["gol23"] = rates_data.get(gol_II, 0)
                sec_data["gol45"] = rates_data.get(gol_IV, 0)
                
                new_sec = TollSection(**sec_data)
                db.add(new_sec)
                db.flush()

                for gol, rate in rates_data.items():
                    if gol:
                        db.add(TollSectionRate(
                            section_id=new_sec.id,
                            golongan_id=gol.id,
                            rate=rate
                        ))
                added_count += 1
                print(f"Menambahkan ruas: {sec_data['name']}")
            else:
                print(f"Ruas sudah ada: {sec_data['name']}")

        db.commit()
        print(f"Selesai! {added_count} ruas berhasil ditambahkan.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
