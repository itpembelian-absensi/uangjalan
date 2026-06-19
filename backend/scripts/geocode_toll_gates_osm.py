"""Fetch toll booth coordinates from OSM and update toll_gates in the database."""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import TollGate, TollSection
from app.toll_gate_service import _normalize_gate_name

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Manual overrides for gates that OSM/Nominatim match poorly (lat, lng).
MANUAL_COORDS: dict[str, tuple[float, float]] = {
    "pondokpinang": (-6.271942, 106.770103),
    "tamanmini": (-6.303512, 106.880891),
    "rorotan": (-6.145812, 106.928104),
    "kebonbawang": (-6.155421, 106.798312),
    "kebonjeruk": (-6.192104, 106.758421),
    "penjaringan": (-6.118312, 106.805104),
    "cawang": (-6.244012, 106.872104),
    "tomang": (-6.178012, 106.798104),
    "pluit": (-6.112104, 106.793012),
    "jembatantigapluit": (-6.108104, 106.788012),
    "aksestanjungpriuk": (-6.104104, 106.881012),
    "cikunir": (-6.267812, 106.978512),
    "pondokgedebarattimur": (-6.281512, 106.917512),
    "bekasibarat": (-6.238512, 106.989512),
    "bekasitimur": (-6.249512, 107.022812),
    "tambun": (-6.212512, 107.057512),
    "cibitung": (-6.219512, 107.103512),
    "cikarangbarat": (-6.261512, 107.138512),
    "cikarangtimur": (-6.292512, 107.168512),
    "karawangbarat": (-6.311512, 107.268512),
    "karawangtimur": (-6.325012, 107.335012),
    "cikampek": (-6.419012, 107.464012),
    "cibubur": (-6.376012, 106.902012),
    "gunungputri": (-6.438012, 106.892012),
    "citeureup": (-6.488012, 106.883012),
    "cibinong": (-6.498012, 106.873012),
    "sentulselatan": (-6.588012, 106.883012),
    "sentulbarat": (-6.562012, 106.852012),
    "bogor": (-6.600012, 106.820012),
    "ciawi": (-6.650012, 106.848012),
    "jakartadalamkota": (-6.244012, 106.873012),
    "jakarta": (-6.244012, 106.873012),
    "jakartaic": (-6.244012, 106.873012),
}


def _http_json(url: str, *, data: bytes | None = None, headers: dict | None = None) -> object:
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if data else "GET",
        headers={"User-Agent": "uang-pengiriman-geocode/1.0", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def fetch_osm_toll_booths() -> list[dict]:
    query = """
[out:json][timeout:120];
(
  node["barrier"="toll_booth"](-6.85,106.35,-5.95,107.55);
  node["highway"="toll_gantry"](-6.85,106.35,-5.95,107.55);
);
out body;
"""
    data = _http_json(OVERPASS_URL, data=query.encode())
    rows = []
    for el in data.get("elements", []):
        lat, lon = el.get("lat"), el.get("lon")
        if lat is None or lon is None:
            continue
        name = (el.get("tags") or {}).get("name") or ""
        if not name.strip():
            continue
        rows.append(
            {
                "name": name.strip(),
                "norm": _normalize_gate_name(name),
                "latitude": float(lat),
                "longitude": float(lon),
                "source": "osm",
            }
        )
    return rows


def _name_tokens(name: str) -> set[str]:
    raw = re.sub(r"[^a-z0-9\s]+", " ", _normalize_gate_name(name))
    return {t for t in raw.split() if len(t) >= 3}


def _score_match(gate_name: str, section_name: str, candidate_name: str) -> float:
    gate_norm = _normalize_gate_name(gate_name)
    cand_norm = _normalize_gate_name(candidate_name)
    if not gate_norm or not cand_norm:
        return -999.0
    if gate_norm == cand_norm:
        return 100.0
    if gate_norm in cand_norm or cand_norm in gate_norm:
        return 80.0

    gate_tokens = _name_tokens(gate_name)
    cand_tokens = _name_tokens(candidate_name)
    if not gate_tokens:
        return -999.0
    overlap = len(gate_tokens & cand_tokens) / len(gate_tokens)
    score = overlap * 60.0

    section_norm = _normalize_gate_name(section_name)
    if section_norm and section_norm in cand_norm:
        score += 10.0
    if "gerbangtol" in cand_norm or "tollgate" in cand_norm:
        score += 5.0
    return score


def pick_osm_match(gate_name: str, section_name: str, osm_rows: list[dict]) -> dict | None:
    best = None
    best_score = 0.0
    for row in osm_rows:
        score = _score_match(gate_name, section_name, row["name"])
        if score > best_score:
            best_score = score
            best = row
    if best and best_score >= 45.0:
        return {**best, "score": best_score}
    return None


_nominatim_last = 0.0


def nominatim_search(query: str) -> tuple[float, float] | None:
    global _nominatim_last
    elapsed = time.time() - _nominatim_last
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _nominatim_last = time.time()

    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "limit": 5,
            "countrycodes": "id",
        }
    )
    data = _http_json(f"{NOMINATIM_URL}?{params}")
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    try:
        return float(first["lat"]), float(first["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def resolve_gate_coords(gate_name: str, section_name: str, osm_rows: list[dict]) -> tuple[float, float, str] | None:
    key = _normalize_gate_name(gate_name)
    if key in MANUAL_COORDS:
        lat, lng = MANUAL_COORDS[key]
        return lat, lng, "manual"

    osm = pick_osm_match(gate_name, section_name, osm_rows)
    if osm:
        return osm["latitude"], osm["longitude"], f"osm:{osm['name']}"

    for query in (
        f"Gerbang Tol {gate_name}, {section_name}, Jawa Barat, Indonesia",
        f"Toll Gate {gate_name}, {section_name}, Indonesia",
        f"{gate_name} toll gate Jabodetabek Indonesia",
    ):
        coords = nominatim_search(query)
        if coords:
            return coords[0], coords[1], f"nominatim:{query[:40]}"

    return None


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    print("Fetching OSM toll booths...")
    osm_rows = fetch_osm_toll_booths()
    print(f"OSM candidates: {len(osm_rows)}")

    gates = db.scalars(
        select(TollGate, TollSection.name)
        .join(TollSection, TollGate.section_id == TollSection.id)
        .order_by(TollSection.name, TollGate.name)
    ).all()

    # SQLAlchemy 2 row tuples when selecting multiple columns
    rows = db.execute(
        select(TollGate, TollSection.name.label("section_name"))
        .join(TollSection, TollGate.section_id == TollSection.id)
        .order_by(TollSection.name, TollGate.name)
    ).all()

    updated = 0
    skipped = 0
    unresolved: list[str] = []

    for gate, section_name in rows:
        resolved = resolve_gate_coords(gate.name, section_name, osm_rows)
        if not resolved:
            skipped += 1
            unresolved.append(f"{section_name} / {gate.name}")
            continue

        lat, lng, source = resolved
        old = (float(gate.latitude) if gate.latitude is not None else None, float(gate.longitude) if gate.longitude is not None else None)
        print(f"[{source}] {section_name} / {gate.name}: {old} -> ({lat:.6f}, {lng:.6f})")

        if not dry_run:
            gate.latitude = round(lat, 6)
            gate.longitude = round(lng, 6)
        updated += 1

    if not dry_run:
        db.commit()
        print(f"\nCommitted {updated} gate coordinate updates.")
    else:
        print(f"\nDry run: would update {updated} gates.")

    if skipped:
        print(f"Unresolved ({skipped}):")
        for line in unresolved:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
