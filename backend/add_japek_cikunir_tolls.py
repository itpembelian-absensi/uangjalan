"""
Upsert ruas Jakarta-Cikampek dari gerbang masuk Cikunir.

Tarif diturunkan dari matriks resmi Jakarta IC (Kepmen 250/KPTS/M/2024):
  rate(Cikunir → X) = rate(Jakarta IC → X) − rate(Jakarta IC → Cikunir)
Untuk tujuan satu zona dengan Cikunir (Bekasi/Tambun/Cibitung/Cikarang Barat),
selisih 0 → dipakai selisih zona Pondok Gede→Cikunir sebagai tarif minimum ruas pendek.
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import TollGolongan, TollSection, TollSectionRate

NETWORK = "Trans Jawa"
SECTION_PREFIX = "Jakarta-Cikampek · Cikunir →"
ORIGIN = "Cikunir"
LENGTH_KM = 73.0

# Jakarta IC → Cikunir (zona 2)
JIC_CIKUNIR = {"I": 9500, "II": 14000, "III": 14000, "IV": 19000, "V": 19000}
# Jakarta IC → Pondok Gede (zona 1) — dipakai lantai minimum zona sama
JIC_PONDOK = {"I": 5500, "II": 8000, "III": 8000, "IV": 11000, "V": 11000}

# Jakarta IC → tujuan (Kepmen 250/2024)
JIC_TO_EXIT: dict[str, dict[str, int]] = {
    "Bekasi Barat": {"I": 9500, "II": 14000, "III": 14000, "IV": 19000, "V": 19000},
    "Bekasi Timur": {"I": 9500, "II": 14000, "III": 14000, "IV": 19000, "V": 19000},
    "Tambun": {"I": 9500, "II": 14000, "III": 14000, "IV": 19000, "V": 19000},
    "Cibitung": {"I": 9500, "II": 14000, "III": 14000, "IV": 19000, "V": 19000},
    "Cikarang Barat": {"I": 9500, "II": 14000, "III": 14000, "IV": 19000, "V": 19000},
    "Cibatu": {"I": 16500, "II": 24500, "III": 24500, "IV": 32500, "V": 32500},
    "Cikarang Timur": {"I": 16500, "II": 24500, "III": 24500, "IV": 32500, "V": 32500},
    "Karawang Barat": {"I": 16500, "II": 24500, "III": 24500, "IV": 32500, "V": 32500},
    "Karawang Timur": {"I": 27000, "II": 40500, "III": 40500, "IV": 54000, "V": 54000},
    "Dawuan": {"I": 27000, "II": 40500, "III": 40500, "IV": 54000, "V": 54000},
    "Kalihurip": {"I": 27000, "II": 40500, "III": 40500, "IV": 54000, "V": 54000},
    "Cikampek": {"I": 27000, "II": 40500, "III": 40500, "IV": 54000, "V": 54000},
}

# sort_order setelah varian Jakarta IC (274)
EXITS: list[tuple[str, int]] = [
    ("Bekasi Barat", 280),
    ("Bekasi Timur", 281),
    ("Tambun", 282),
    ("Cibitung", 283),
    ("Cikarang Barat", 284),
    ("Cibatu", 285),
    ("Cikarang Timur", 286),
    ("Karawang Barat", 287),
    ("Karawang Timur", 288),
    ("Dawuan", 289),
    ("Kalihurip", 290),
    ("Cikampek", 291),
]


def _rates_from_cikunir(jic_exit: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for code in ("I", "II", "III", "IV", "V"):
        diff = int(jic_exit[code]) - int(JIC_CIKUNIR[code])
        if diff <= 0:
            diff = int(JIC_CIKUNIR[code]) - int(JIC_PONDOK[code])
        out[code] = diff
    return out


def main() -> None:
    db = SessionLocal()
    try:
        gol_map = {g.code: g for g in db.query(TollGolongan).all()}
        for code in JIC_CIKUNIR:
            if code not in gol_map:
                raise SystemExit(f"Golongan {code} belum ada di database")

        for destination, sort_order in EXITS:
            rates = _rates_from_cikunir(JIC_TO_EXIT[destination])
            section_name = f"{SECTION_PREFIX}{destination}"
            section = (
                db.query(TollSection)
                .filter(
                    TollSection.name == section_name,
                    TollSection.origin_name == ORIGIN,
                    TollSection.destination_name == destination,
                )
                .first()
            )
            if not section:
                # Juga cocokkan pola nama lama jika sudah ada
                section = (
                    db.query(TollSection)
                    .filter(
                        TollSection.origin_name == ORIGIN,
                        TollSection.destination_name == destination,
                        TollSection.name.ilike("%Cikampek%"),
                    )
                    .first()
                )
            if not section:
                section = TollSection(
                    network=NETWORK,
                    name=section_name,
                    origin_name=ORIGIN,
                    destination_name=destination,
                    length_km=LENGTH_KM,
                    gol23=rates["II"],
                    gol45=rates["IV"],
                    sort_order=sort_order,
                    is_active=True,
                )
                db.add(section)
                db.flush()
                print(f"[NEW] {ORIGIN} → {destination} id={section.id}")
            else:
                section.network = NETWORK
                section.name = section_name
                section.length_km = LENGTH_KM
                section.gol23 = rates["II"]
                section.gol45 = rates["IV"]
                section.sort_order = sort_order
                section.is_active = True
                print(f"[UPDATE] {ORIGIN} → {destination} id={section.id}")

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
        print("Selesai upsert Japek Cikunir → exits.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
