from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import TollGate, TollGateFare, TollGolongan, TollSection, TollSectionRate
from app.toll_gate_service import gate_coordinate_lookup

BPJT_TARIF_PAGE = "https://bpjt.pu.go.id/info-tarif-dan-golongan/"
BPJT_JABODETABEK_API = "https://bpjt.pu.go.id/wp-json/wp/v2/tarif_dan_golongan/2785"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "bpjt_jabodetabek.json"
GATES_FILE = DATA_DIR / "bpjt_jabodetabek_gates.json"
EXTRA_PACK_FILES = [
    DATA_DIR / "bpjt_trans_jawa_japek.json",
]
LEGACY_SECTION_NAMES = {
    "japek (jakarta–cikampek)",
    "japek (jakarta-cikampek)",
    "jorr",
    "dalam kota & sedyatmo",
    "jagorawi",
}
USER_AGENT = "UangPengiriman/1.0 (+bpjt-import)"


def _http_get_json(url: str, timeout: int = 30) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def fetch_bpjt_jabodetabek_meta() -> dict:
    """Ambil metadata resmi PDF Jabodetabek dari API WordPress BPJT."""
    meta = {
        "source_page": BPJT_TARIF_PAGE,
        "source_api": BPJT_JABODETABEK_API,
        "pdf_url": None,
        "title": "Tarif Tol JABODETABEK",
        "modified": None,
    }
    payload = _http_get_json(BPJT_JABODETABEK_API)
    if isinstance(payload, dict):
        meta["title"] = (payload.get("title") or {}).get("rendered") or meta["title"]
        meta["modified"] = payload.get("modified")
        media_id = ((payload.get("acf") or {}).get("pdf_tarif_dan_golongan") or {}).get("value")
        if media_id:
            media = _http_get_json(f"https://bpjt.pu.go.id/wp-json/wp/v2/media/{media_id}")
            if isinstance(media, dict):
                meta["pdf_url"] = media.get("source_url")
    if not meta["pdf_url"] and DATA_FILE.exists():
        cached = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        meta["pdf_url"] = cached.get("pdf_url")
    return meta


def _load_json_pack(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Dataset BPJT tidak ditemukan: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_jabodetabek_dataset() -> dict:
    return _load_json_pack(DATA_FILE)


def load_jabodetabek_gates_dataset() -> dict:
    if not GATES_FILE.exists():
        raise FileNotFoundError(
            f"Dataset gerbang BPJT tidak ditemukan: {GATES_FILE}. "
            "Jalankan backend/scripts/build_bpjt_gates_json.py"
        )
    return _load_json_pack(GATES_FILE)


def _ensure_golongan(db: Session) -> dict[str, TollGolongan]:
    defaults = [
        ("Golongan I", "I", "Kendaraan ringan (mobil, motor)", 0),
        ("Golongan II", "II", "Truk 2 gandar (engkel, box, dll.)", 1),
        ("Golongan III", "III", "Truk 3 gandar (tronton)", 2),
        ("Golongan IV", "IV", "Truk 4 gandar", 3),
        ("Golongan V", "V", "Truk 5 gandar atau lebih (trailer/gandeng)", 4),
    ]
    by_code: dict[str, TollGolongan] = {}
    for row in db.scalars(select(TollGolongan)).all():
        by_code[row.code.upper()] = row
    for name, code, desc, sort_order in defaults:
        if code not in by_code:
            obj = TollGolongan(
                name=name, code=code, description=desc, sort_order=sort_order, is_active=True
            )
            db.add(obj)
            db.flush()
            by_code[code] = obj
    return by_code


def _section_key(network: str, name: str, origin: str | None, destination: str | None) -> tuple:
    return (
        (network or "").strip().lower(),
        (name or "").strip().lower(),
        (origin or "").strip().lower(),
        (destination or "").strip().lower(),
    )


def _find_existing_section(
    db: Session, network: str, name: str, origin: str | None, destination: str | None
) -> TollSection | None:
    key = _section_key(network, name, origin, destination)
    for row in db.scalars(
        select(TollSection).options(selectinload(TollSection.rates).selectinload(TollSectionRate.golongan))
    ).all():
        if _section_key(row.network or "", row.name, row.origin_name, row.destination_name) == key:
            return row
    return None


def _find_section_by_name(db: Session, network: str, section_name: str) -> TollSection | None:
    target = re.sub(r"[^a-z0-9]+", "", (section_name or "").lower())
    for row in db.scalars(select(TollSection)).all():
        if (row.network or "").strip().lower() != network.lower():
            continue
        if re.sub(r"[^a-z0-9]+", "", row.name.lower()) == target:
            return row
    return None


def _apply_rates(db: Session, section: TollSection, rates: dict, gol_by_code: dict[str, TollGolongan]) -> None:
    db.execute(delete(TollSectionRate).where(TollSectionRate.section_id == section.id))
    db.flush()
    gol23 = 0.0
    gol45 = 0.0
    for code, amount in rates.items():
        gol = gol_by_code.get(code.upper())
        if not gol:
            continue
        value = float(amount)
        db.add(TollSectionRate(section_id=section.id, golongan_id=gol.id, rate=value))
        if code.upper() in ("II", "III") and value > 0:
            gol23 = value if code.upper() == "II" else gol23 or value
        if code.upper() in ("IV", "V") and value > 0:
            gol45 = value if code.upper() == "IV" else gol45 or value
    section.gol23 = gol23
    section.gol45 = gol45


def _deactivate_legacy_sections(db: Session) -> None:
    for row in db.scalars(select(TollSection)).all():
        if row.name.strip().lower() in LEGACY_SECTION_NAMES and (
            row.network is None or row.network == "" or row.network.strip().lower() == "jabodetabek"
        ):
            row.is_active = False


def _import_sections_from_pack(db: Session, pack: dict) -> tuple[int, int]:
    network = (pack.get("network") or "Jabodetabek").strip()
    gol_by_code = _ensure_golongan(db)
    created = 0
    updated = 0

    for item in pack.get("sections", []):
        name = item["name"].strip()
        origin = (item.get("origin_name") or "").strip() or None
        destination = (item.get("destination_name") or "").strip() or None
        existing = _find_existing_section(db, network, name, origin, destination)
        if existing:
            existing.network = network
            existing.name = name
            existing.origin_name = origin
            existing.destination_name = destination
            existing.length_km = float(item.get("length_km") or 1)
            existing.sort_order = int(item.get("sort_order") or 0)
            existing.is_active = True
            _apply_rates(db, existing, item.get("rates") or {}, gol_by_code)
            updated += 1
        else:
            section = TollSection(
                network=network,
                name=name,
                origin_name=origin,
                destination_name=destination,
                length_km=float(item.get("length_km") or 1),
                sort_order=int(item.get("sort_order") or 0),
                is_active=True,
                gol23=0,
                gol45=0,
            )
            db.add(section)
            db.flush()
            _apply_rates(db, section, item.get("rates") or {}, gol_by_code)
            created += 1

    return created, updated


def _gate_code(name: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", name.upper()).strip("_")[:24] or "GT"
    code = base
    n = 2
    while code in used:
        code = f"{base[:20]}_{n}"
        n += 1
    used.add(code)
    return code


def _upsert_gate(
    db: Session,
    section_id: int,
    name: str,
    by_name: dict[str, TollGate],
    used_codes: set[str],
    sort_order: int,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> TollGate:
    key = name.strip().lower()
    if latitude is None or longitude is None:
        builtin = gate_coordinate_lookup(name)
        if builtin:
            latitude, longitude = builtin
    if key in by_name:
        gate = by_name[key]
        gate.name = name.strip()
        gate.is_active = True
        if latitude is not None and longitude is not None:
            gate.latitude = latitude
            gate.longitude = longitude
        return gate
    code = _gate_code(name, used_codes)
    gate = TollGate(
        section_id=section_id,
        code=code,
        name=name.strip(),
        latitude=latitude,
        longitude=longitude,
        sort_order=sort_order,
        is_active=True,
    )
    db.add(gate)
    db.flush()
    by_name[key] = gate
    return gate


def _import_gate_matrices_from_pack(
    db: Session, pack: dict, gol_by_code: dict[str, TollGolongan]
) -> dict:
    network = (pack.get("network") or "Jabodetabek").strip()
    sections_imported = 0
    sections_skipped: list[str] = []
    gates_created = 0
    gates_updated = 0
    fares_created = 0

    for matrix in pack.get("matrices", []):
        section_name = matrix.get("section_name", "").strip()
        section = _find_section_by_name(db, network, section_name)
        if not section:
            sections_skipped.append(f"{network}: {section_name}")
            continue

        fares_data = matrix.get("fares") or []
        if not fares_data:
            continue

        existing_gates = db.scalars(
            select(TollGate).where(TollGate.section_id == section.id)
        ).all()
        by_name: dict[str, TollGate] = {g.name.strip().lower(): g for g in existing_gates}
        used_codes = {g.code for g in existing_gates}

        gate_names: list[str] = []
        for fare in fares_data:
            gate_names.append(fare["entry"])
            gate_names.append(fare["exit"])
        unique_names = list(dict.fromkeys(gate_names))

        gate_by_name: dict[str, TollGate] = {}
        for idx, gname in enumerate(unique_names):
            before = gname.strip().lower() in by_name
            gate = _upsert_gate(db, section.id, gname, by_name, used_codes, idx + 1)
            gate_by_name[gname.strip().lower()] = gate
            if before:
                gates_updated += 1
            else:
                gates_created += 1

        gate_ids = [g.id for g in gate_by_name.values()]
        if gate_ids:
            db.execute(
                delete(TollGateFare).where(
                    (TollGateFare.entry_gate_id.in_(gate_ids))
                    | (TollGateFare.exit_gate_id.in_(gate_ids))
                )
            )
            db.flush()

        for fare in fares_data:
            entry = gate_by_name.get(fare["entry"].strip().lower())
            exit_gate = gate_by_name.get(fare["exit"].strip().lower())
            if not entry or not exit_gate or entry.id == exit_gate.id:
                continue
            for code, amount in (fare.get("rates") or {}).items():
                gol = gol_by_code.get(code.upper())
                if not gol:
                    continue
                db.add(
                    TollGateFare(
                        entry_gate_id=entry.id,
                        exit_gate_id=exit_gate.id,
                        golongan_id=gol.id,
                        rate=float(amount),
                    )
                )
                fares_created += 1

        sections_imported += 1

    return {
        "sections_imported": sections_imported,
        "sections_skipped": sections_skipped,
        "gates_created": gates_created,
        "gates_updated": gates_updated,
        "fares_created": fares_created,
    }


def _deactivate_exit_variant_sections(db: Session) -> int:
    """Nonaktifkan baris ruas duplikat (nama sama, gerbang keluar beda) — sisakan tarif ruas penuh."""
    rows = db.scalars(select(TollSection).where(TollSection.is_active.is_(True))).all()
    by_key: dict[tuple[str, str], list[TollSection]] = {}
    for row in rows:
        if (row.network or "").strip().lower() == "trans jawa":
            continue
        key = ((row.network or "").strip().lower(), row.name.strip().lower())
        by_key.setdefault(key, []).append(row)

    deactivated = 0
    for group in by_key.values():
        if len(group) <= 1:
            continue
        best = max(group, key=lambda r: float(r.gol23 or 0))
        for row in group:
            if row.id != best.id:
                row.is_active = False
                deactivated += 1
    return deactivated


def _renumber_sort_orders(db: Session) -> None:
    """Beri nomor urut unik lintas semua jaringan agar tidak ada sort_order dobel."""
    rows = db.scalars(
        select(TollSection).order_by(
            TollSection.network.asc(),
            TollSection.sort_order.asc(),
            TollSection.name.asc(),
            TollSection.id.asc(),
        )
    ).all()
    for idx, row in enumerate(rows, start=1):
        row.sort_order = idx


def import_jabodetabek_sections(db: Session, *, deactivate_legacy: bool = True) -> dict:
    """Impor/upsert ruas tol dari semua paket dataset BPJT."""
    meta = fetch_bpjt_jabodetabek_meta()
    packs = [load_jabodetabek_dataset(), *[_load_json_pack(p) for p in EXTRA_PACK_FILES if p.exists()]]
    if deactivate_legacy:
        _deactivate_legacy_sections(db)

    total_created = 0
    total_updated = 0
    for pack in packs:
        created, updated = _import_sections_from_pack(db, pack)
        total_created += created
        total_updated += updated

    deactivated_variants = _deactivate_exit_variant_sections(db)

    # Re-number agar sort_order unik lintas semua jaringan
    _renumber_sort_orders(db)

    db.commit()
    return {
        "network": "BPJT (Jabodetabek + Trans Jawa)",
        "created": total_created,
        "updated": total_updated,
        "deactivated_variants": deactivated_variants,
        "total": total_created + total_updated,
        "source_title": meta.get("title") or "Tarif Tol BPJT",
        "source_page": meta.get("source_page") or BPJT_TARIF_PAGE,
        "pdf_url": meta.get("pdf_url"),
        "source_modified": meta.get("modified"),
    }


def import_jabodetabek_gate_matrices(db: Session) -> dict:
    """Impor matriks gerbang dari semua paket dataset BPJT."""
    jabodetabek_gates = load_jabodetabek_gates_dataset()
    packs = [jabodetabek_gates, *[_load_json_pack(p) for p in EXTRA_PACK_FILES if p.exists()]]
    gol_by_code = _ensure_golongan(db)

    totals = {
        "sections_imported": 0,
        "sections_skipped": [],
        "gates_created": 0,
        "gates_updated": 0,
        "fares_created": 0,
    }
    for pack in packs:
        result = _import_gate_matrices_from_pack(db, pack, gol_by_code)
        totals["sections_imported"] += result["sections_imported"]
        totals["sections_skipped"].extend(result["sections_skipped"])
        totals["gates_created"] += result["gates_created"]
        totals["gates_updated"] += result["gates_updated"]
        totals["fares_created"] += result["fares_created"]

    db.commit()
    return {
        "network": "BPJT (Jabodetabek + Trans Jawa)",
        **totals,
        "source": "Tarif Tol BPJT",
        "source_url": BPJT_TARIF_PAGE,
    }


def import_jabodetabek_all(db: Session, *, deactivate_legacy: bool = True) -> dict:
    sections_result = import_jabodetabek_sections(db, deactivate_legacy=deactivate_legacy)
    gates_result = import_jabodetabek_gate_matrices(db)
    return {
        "sections": sections_result,
        "gates": gates_result,
    }
