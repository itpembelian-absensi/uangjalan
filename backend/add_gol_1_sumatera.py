import sys
import os

# Menambahkan path backend ke sys.path agar bisa import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollSection, TollGolongan, TollSectionRate

def main():
    db = SessionLocal()
    try:
        gol_I = db.query(TollGolongan).filter_by(code="I").first()
        if not gol_I:
            print("Golongan I tidak ditemukan")
            return

        sections_rates = {
            "Penyeberangan Merak - Bakauheni": 481800, # estimasi Golongan I / Kendaraan Pribadi
            "Bakauheni - Terbanggi Besar": 118500,     # tarif tol Golongan I
            "Tangerang - Merak": 53500                 # tarif tol Golongan I
        }

        for sec_name, rate in sections_rates.items():
            section = db.query(TollSection).filter_by(name=sec_name).first()
            if section:
                # Cek apakah rate untuk gol 1 sudah ada
                existing_rate = db.query(TollSectionRate).filter_by(
                    section_id=section.id,
                    golongan_id=gol_I.id
                ).first()

                if not existing_rate:
                    new_rate = TollSectionRate(
                        section_id=section.id,
                        golongan_id=gol_I.id,
                        rate=rate
                    )
                    db.add(new_rate)
                    print(f"Berhasil menambahkan tarif Gol I untuk {sec_name}: {rate}")
                else:
                    print(f"Tarif Gol I untuk {sec_name} sudah ada")
            else:
                print(f"Ruas {sec_name} tidak ditemukan di database")

        db.commit()
        print("Selesai menambahkan tarif Gol I!")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
