"""
Upsert 2 ruas koridor Kayu Besar → Bintaro:

1. JORR · Kayu Besar → Ulujami
   Tarif flat JORR (Kepmen PUPR 1604/KPTS/M/2023).

2. Pondok Aren-Bintaro Viaduct-Ulujami · Ulujami → Pondok Aren
   Tarif BPJT ruas Pondok Aren–Bintaro Viaduct–Ulujami.
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollGolongan, TollSection, TollSectionRate

SECTIONS = [
    {
        "network": "Jabodetabek",
        "name": "JORR",
        "origin_name": "Kayu Besar",
        "destination_name": "Ulujami",
        "length_km": 18.0,
        "sort_order": 109,
        "rates": {"I": 17000, "II": 25000, "III": 25000, "IV": 33500, "V": 33500},
    },
    {
        "network": "Jabodetabek",
        "name": "Pondok Aren-Bintaro Viaduct-Ulujami",
        "origin_name": "Ulujami",
        "destination_name": "Pondok Aren",
        "length_km": 8.5,
        "sort_order": 110,
        "rates": {"I": 17000, "II": 25000, "III": 25000, "IV": 33500, "V": 33500},
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        gol_map = {g.code: g for g in db.query(TollGolongan).all()}
        for code in ("I", "II", "III", "IV", "V"):
            if code not in gol_map:
                raise SystemExit(f"Golongan {code} belum ada di database")

        for spec in SECTIONS:
            rates = spec["rates"]
            section = (
                db.query(TollSection)
                .filter(
                    TollSection.name == spec["name"],
                    TollSection.origin_name == spec["origin_name"],
                    TollSection.destination_name == spec["destination_name"],
                )
                .first()
            )
            if not section:
                section = TollSection(
                    network=spec["network"],
                    name=spec["name"],
                    origin_name=spec["origin_name"],
                    destination_name=spec["destination_name"],
                    length_km=spec["length_km"],
                    gol23=rates["II"],
                    gol45=rates["IV"],
                    sort_order=spec["sort_order"],
                    is_active=True,
                )
                db.add(section)
                db.flush()
                print(
                    f"[NEW] {spec['name']}: {spec['origin_name']} → "
                    f"{spec['destination_name']} id={section.id}"
                )
            else:
                section.network = spec["network"]
                section.length_km = spec["length_km"]
                section.gol23 = rates["II"]
                section.gol45 = rates["IV"]
                section.sort_order = spec["sort_order"]
                section.is_active = True
                print(
                    f"[UPDATE] {spec['name']}: {spec['origin_name']} → "
                    f"{spec['destination_name']} id={section.id}"
                )

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
        print("Selesai upsert Kayu Besar → Ulujami → Pondok Aren (Bintaro).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
