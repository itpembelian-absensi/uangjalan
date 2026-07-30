"""
Tambah gerbang keluar Karawaci & Bitung pada koridor Jakarta → Tangerang/Merak.

Tarif = tarif resmi integrasi Jakarta–Tangerang / Tomang–Cikupa
(Kepmen PUPR 2692/KPTS/M/2024).
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollGolongan, TollSection, TollSectionRate

SECTION_NAME = "Tangerang - Merak"
NETWORK = "Trans Jawa"
ORIGIN = "Jakarta (Dalam Kota)"
LENGTH_KM = 98.0

# Tarif resmi integrasi Jakarta–Tangerang / Tomang–Cikupa
# (Kepmen PUPR 2692/KPTS/M/2024, berlaku 19 Okt 2024)
RATES = {"I": 8500, "II": 12500, "III": 12500, "IV": 16500, "V": 16500}

# sort_order sebelum Cikupa (39)
EXITS = [
    ("Karawaci", 37),
    ("Bitung", 38),
]


def main() -> None:
    db = SessionLocal()
    try:
        gol_map = {g.code: g for g in db.query(TollGolongan).all()}
        for code in RATES:
            if code not in gol_map:
                raise SystemExit(f"Golongan {code} belum ada di database")

        added = 0
        for destination, sort_order in EXITS:
            existing = (
                db.query(TollSection)
                .filter(
                    TollSection.name == SECTION_NAME,
                    TollSection.origin_name == ORIGIN,
                    TollSection.destination_name == destination,
                )
                .first()
            )
            if existing:
                print(f"[SKIP] Sudah ada: {ORIGIN} → {destination} (id={existing.id})")
                continue

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

            for code, rate in RATES.items():
                db.add(
                    TollSectionRate(
                        section_id=section.id,
                        golongan_id=gol_map[code].id,
                        rate=rate,
                    )
                )

            added += 1
            print(
                f"[NEW] {SECTION_NAME}: {ORIGIN} → {destination} "
                f"(id={section.id}, sort={sort_order}, Gol I={RATES['I']})"
            )

        db.commit()
        print(f"Selesai. {added} ruas ditambahkan.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
