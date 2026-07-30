"""
Upsert ruas JORR dari Kayu Besar ke arah Jati Asih / Priok.

Tarif flat terintegrasi JORR + Akses Tanjung Priok
(Kepmen PUPR 1604/KPTS/M/2023, berlaku 4 Des 2023).
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollGolongan, TollSection, TollSectionRate

SECTION_NAME = "JORR"
NETWORK = "Jabodetabek"
ORIGIN = "Kayu Besar"
LENGTH_KM = 66.0

# Tarif flat JORR (Penjaringan–Rorotan) + ATP
RATES = {"I": 17000, "II": 25000, "III": 25000, "IV": 33500, "V": 33500}

# sort_order setelah master JORR yang sudah ada
EXITS = [
    ("Jati Asih", 102),
    ("Cikunir", 103),
    ("Cilincing", 104),
    ("Kebon Bawang", 105),  # arah Priok / JORR N
]


def main() -> None:
    db = SessionLocal()
    try:
        gol_map = {g.code: g for g in db.query(TollGolongan).all()}
        for code in RATES:
            if code not in gol_map:
                raise SystemExit(f"Golongan {code} belum ada di database")

        for destination, sort_order in EXITS:
            section = (
                db.query(TollSection)
                .filter(
                    TollSection.name == SECTION_NAME,
                    TollSection.origin_name == ORIGIN,
                    TollSection.destination_name == destination,
                )
                .first()
            )
            if not section:
                section = TollSection(
                    network=NETWORK,
                    name=SECTION_NAME,
                    origin_name=ORIGIN,
                    destination_name=destination,
                    length_km=LENGTH_KM,
                    gol23=RATES["II"],
                    gol45=RATES["IV"],
                    sort_order=sort_order,
                    is_active=True,
                )
                db.add(section)
                db.flush()
                print(f"[NEW] {ORIGIN} → {destination} id={section.id}")
            else:
                section.network = NETWORK
                section.length_km = LENGTH_KM
                section.gol23 = RATES["II"]
                section.gol45 = RATES["IV"]
                section.sort_order = sort_order
                section.is_active = True
                print(f"[UPDATE] {ORIGIN} → {destination} id={section.id}")

            for code, rate in RATES.items():
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
            print(f"  rates={RATES}")

        db.commit()
        print("Selesai upsert JORR Kayu Besar.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
