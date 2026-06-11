"""
Insert tarif tol Jagorawi dari gerbang asal Jakarta Dalam Kota
ke berbagai gerbang tujuan (Taman Mini s/d Ciawi).

Data dari tabel resmi BPJT/Jasa Marga.
"""
from app.db import SessionLocal
from app.models import TollSection, TollGate, TollGateFare, TollGolongan

# ----- Data tarif dari tabel -----
# (exit_gate_name, gol_I, gol_II, gol_III, gol_IV, gol_V)
FARES = [
    ("Taman Mini",      8000, 12000, 12000, 17000, 17000),
    ("Cibubur",         8000, 12000, 12000, 17000, 17000),
    ("Gunung Putri",    8000, 12000, 12000, 17000, 17000),
    ("Citeureup",       8000, 12000, 12000, 17000, 17000),
    ("Cibinong",        8000, 12000, 12000, 17000, 17000),
    ("Sentul Selatan",  8000, 12000, 12000, 17000, 17000),
    ("Sentul Barat",    8000, 12000, 12000, 17000, 17000),
    ("Bogor",           8000, 12000, 12000, 17000, 17000),
    ("Ciawi",           8000, 12000, 12000, 17000, 17000),
]

ENTRY_GATE_NAME = "Jakarta Dalam Kota"
SECTION_NETWORK = "Jagorawi"


def make_code(name: str) -> str:
    return name.upper().replace(" ", "_").replace("/", "_")


def main():
    db = SessionLocal()
    try:
        # Load golongan mapping: code -> id
        gol_map: dict[str, int] = {}
        for g in db.query(TollGolongan).all():
            gol_map[g.code] = g.id
        print(f"Golongan: {gol_map}")

        required_codes = ["I", "II", "III", "IV", "V"]
        for code in required_codes:
            if code not in gol_map:
                raise ValueError(f"Golongan {code} belum ada di database!")

        created_sections = 0
        created_gates = 0
        created_fares = 0
        skipped_fares = 0

        for exit_name, gol1, gol2, gol3, gol4, gol5 in FARES:
            section_name = f"Jagorawi"
            origin = ENTRY_GATE_NAME
            destination = exit_name

            # Find or create TollSection
            section = (
                db.query(TollSection)
                .filter(
                    TollSection.name == section_name,
                    TollSection.origin_name == origin,
                    TollSection.destination_name == destination,
                )
                .first()
            )
            if not section:
                # Get max sort_order for Jagorawi sections
                max_sort = (
                    db.query(TollSection.sort_order)
                    .filter(TollSection.name.ilike("%jagorawi%"))
                    .order_by(TollSection.sort_order.desc())
                    .first()
                )
                next_sort = (max_sort[0] + 1) if max_sort else 50
                section = TollSection(
                    network=SECTION_NETWORK,
                    name=section_name,
                    origin_name=origin,
                    destination_name=destination,
                    length_km=1,  # placeholder
                    gol23=gol2,
                    gol45=gol4,
                    sort_order=next_sort,
                    is_active=True,
                )
                db.add(section)
                db.flush()
                created_sections += 1
                print(f"  [NEW] Section: {section_name} ({origin} → {destination}), id={section.id}")
            else:
                print(f"  [EXISTS] Section: {section_name} ({origin} → {destination}), id={section.id}")

            # Find or create entry gate
            entry_code = make_code(ENTRY_GATE_NAME)
            entry_gate = (
                db.query(TollGate)
                .filter(
                    TollGate.section_id == section.id,
                    TollGate.code == entry_code,
                )
                .first()
            )
            if not entry_gate:
                entry_gate = TollGate(
                    section_id=section.id,
                    code=entry_code,
                    name=ENTRY_GATE_NAME,
                    sort_order=1,
                    is_active=True,
                )
                db.add(entry_gate)
                db.flush()
                created_gates += 1
                print(f"    [NEW] Entry gate: {ENTRY_GATE_NAME}, id={entry_gate.id}")

            # Find or create exit gate
            exit_code = make_code(exit_name)
            exit_gate = (
                db.query(TollGate)
                .filter(
                    TollGate.section_id == section.id,
                    TollGate.code == exit_code,
                )
                .first()
            )
            if not exit_gate:
                exit_gate = TollGate(
                    section_id=section.id,
                    code=exit_code,
                    name=exit_name,
                    sort_order=2,
                    is_active=True,
                )
                db.add(exit_gate)
                db.flush()
                created_gates += 1
                print(f"    [NEW] Exit gate: {exit_name}, id={exit_gate.id}")

            # Insert fares for each golongan
            fare_data = [
                ("I", gol1),
                ("II", gol2),
                ("III", gol3),
                ("IV", gol4),
                ("V", gol5),
            ]
            for gol_code, rate in fare_data:
                gol_id = gol_map[gol_code]
                existing = (
                    db.query(TollGateFare)
                    .filter(
                        TollGateFare.entry_gate_id == entry_gate.id,
                        TollGateFare.exit_gate_id == exit_gate.id,
                        TollGateFare.golongan_id == gol_id,
                    )
                    .first()
                )
                if existing:
                    if float(existing.rate) != float(rate):
                        existing.rate = rate
                        print(f"    [UPDATE] Fare {gol_code}: {rate}")
                    else:
                        skipped_fares += 1
                else:
                    fare = TollGateFare(
                        entry_gate_id=entry_gate.id,
                        exit_gate_id=exit_gate.id,
                        golongan_id=gol_id,
                        rate=rate,
                    )
                    db.add(fare)
                    created_fares += 1

        db.commit()
        print()
        print(f"=== Selesai ===")
        print(f"  Sections dibuat: {created_sections}")
        print(f"  Gates dibuat: {created_gates}")
        print(f"  Fares dibuat: {created_fares}")
        print(f"  Fares sudah ada: {skipped_fares}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
