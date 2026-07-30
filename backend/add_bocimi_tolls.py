"""
Upsert Tol Bocimi (Bogor–Ciawi–Sukabumi) seksi 1–2: Ciawi → Cibadak.

Tarif Kepmen PUPR 1661/KPTS/M/2024 (Seksi 2 bertarif 12 Okt 2024)
+ acuan Seksi 1 Ciawi–Cigombong.
Seksi 3 Cibadak–Sukabumi belum beroperasi — tidak diimpor.
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollGolongan, TollSection, TollSectionRate

SECTION_NAME = "Bocimi"
NETWORK = "Jawa Barat"
LENGTH_KM = 39.0

# (origin, destination, sort_order, rates I..V)
PAIRS = [
    ("Ciawi", "Cigombong", 106, {"I": 19000, "II": 28000, "III": 28000, "IV": 37500, "V": 37500}),
    ("Ciawi", "Parungkuda (Cibadak)", 107, {"I": 36000, "II": 53000, "III": 53000, "IV": 71000, "V": 71000}),
    ("Caringin", "Cigombong", 108, {"I": 19000, "II": 28000, "III": 28000, "IV": 37500, "V": 37500}),
    ("Caringin", "Parungkuda (Cibadak)", 109, {"I": 36000, "II": 53000, "III": 53000, "IV": 71000, "V": 71000}),
    ("Cigombong", "Parungkuda (Cibadak)", 110, {"I": 17000, "II": 25000, "III": 25000, "IV": 33500, "V": 33500}),
]


def main() -> None:
    db = SessionLocal()
    try:
        gol_map = {g.code: g for g in db.query(TollGolongan).all()}
        for code in ("I", "II", "III", "IV", "V"):
            if code not in gol_map:
                raise SystemExit(f"Golongan {code} belum ada di database")

        for origin, destination, sort_order, rates in PAIRS:
            section = (
                db.query(TollSection)
                .filter(
                    TollSection.name == SECTION_NAME,
                    TollSection.origin_name == origin,
                    TollSection.destination_name == destination,
                )
                .first()
            )
            if not section:
                section = TollSection(
                    network=NETWORK,
                    name=SECTION_NAME,
                    origin_name=origin,
                    destination_name=destination,
                    length_km=LENGTH_KM,
                    gol23=rates["II"],
                    gol45=rates["IV"],
                    sort_order=sort_order,
                    is_active=True,
                )
                db.add(section)
                db.flush()
                print(f"[NEW] {origin} → {destination} id={section.id}")
            else:
                section.network = NETWORK
                section.length_km = LENGTH_KM
                section.gol23 = rates["II"]
                section.gol45 = rates["IV"]
                section.sort_order = sort_order
                section.is_active = True
                print(f"[UPDATE] {origin} → {destination} id={section.id}")

            for code, rate in rates.items():
                row = (
                    db.query(TollSectionRate)
                    .filter_by(section_id=section.id, golongan_id=gol_map[code].id)
                    .first()
                )
                if row:
                    row.rate = rate
                else:
                    db.add(
                        TollSectionRate(
                            section_id=section.id,
                            golongan_id=gol_map[code].id,
                            rate=rate,
                        )
                    )
            print(f"  rates={rates}")

        db.commit()
        print("Selesai upsert Bocimi Ciawi–Cibadak.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
