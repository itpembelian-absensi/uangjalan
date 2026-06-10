from __future__ import annotations

import math

TOLL_NOTE_BPJT = (
    "Tarif berdasarkan master gerbang tol (acuan BPJT / Jasa Marga). "
    "Gerbang masuk/keluar dipilih otomatis dari koordinat gudang dan customer. "
    "Total pulang-pergi dikali 2."
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _fare_index(fares: list[dict]) -> dict[tuple[int, int, str], float]:
    index: dict[tuple[int, int, str], float] = {}
    for row in fares:
        key = (row["entry_gate_id"], row["exit_gate_id"], row["golongan_code"])
        index[key] = float(row["rate"])
    return index


def _nearest_gate(lat: float, lng: float, gates: list[dict]) -> dict | None:
    best: dict | None = None
    best_dist = float("inf")
    for gate in gates:
        glat = gate.get("latitude")
        glng = gate.get("longitude")
        if glat is None or glng is None:
            continue
        dist = haversine_km(lat, lng, float(glat), float(glng))
        if dist < best_dist:
            best_dist = dist
            best = {**gate, "_distance_km": dist}
    return best


def estimate_toll_bpjt_gates(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    gates: list[dict],
    fares: list[dict],
    golongan_code: str = "II",
) -> tuple[float, str] | None:
    """
    Hitung tarif tol satu arah dari matriks gerbang BPJT/Jasa Marga.
    Return (one_way_idr, keterangan) atau None jika tidak ada pasangan tarif.
    """
    if not gates or not fares:
        return None

    index = _fare_index(fares)
    gol = (golongan_code or "II").strip().upper()

    by_section: dict[int, list[dict]] = {}
    for gate in gates:
        if not gate.get("is_active", True):
            continue
        sid = gate["section_id"]
        by_section.setdefault(sid, []).append(gate)

    best: tuple[float, str] | None = None
    best_score = float("inf")

    for section_gates in by_section.values():
        entry = _nearest_gate(origin_lat, origin_lng, section_gates)
        exit_gate = _nearest_gate(dest_lat, dest_lng, section_gates)
        if not entry or not exit_gate:
            continue
        if entry["id"] == exit_gate["id"]:
            continue

        rate = index.get((entry["id"], exit_gate["id"], gol))
        if rate is None and gol in ("III",):
            rate = index.get((entry["id"], exit_gate["id"], "II"))
        if rate is None or rate <= 0:
            continue

        score = entry["_distance_km"] + exit_gate["_distance_km"]
        desc = (
            f"{entry.get('code') or entry.get('name')} → "
            f"{exit_gate.get('code') or exit_gate.get('name')} "
            f"({entry.get('section_name') or 'ruas tol'})"
        )
        if score < best_score:
            best_score = score
            best = (rate, desc)

    return best


def serialize_gate_fare_context(gates_rows, fare_rows) -> dict:
    gates = [
        {
            "id": g.id,
            "section_id": g.section_id,
            "section_name": g.section.name if g.section else None,
            "code": g.code,
            "name": g.name,
            "latitude": float(g.latitude) if g.latitude is not None else None,
            "longitude": float(g.longitude) if g.longitude is not None else None,
            "sort_order": g.sort_order,
            "is_active": g.is_active,
        }
        for g in gates_rows
    ]
    fares = [
        {
            "entry_gate_id": f.entry_gate_id,
            "exit_gate_id": f.exit_gate_id,
            "golongan_code": gol_code,
            "rate": float(f.rate),
        }
        for f, gol_code in fare_rows
    ]
    return {"gates": gates, "fares": fares}
