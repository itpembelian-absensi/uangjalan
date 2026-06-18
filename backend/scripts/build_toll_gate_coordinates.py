"""Build toll gate coordinate dataset from OSM + Nominatim and optionally apply to DB."""
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

from app.toll_gate_service import _normalize_gate_name

DATA_DIR = backend_dir / "data"
OUT_FILE = DATA_DIR / "toll_gate_coordinates.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Search hints when gate name alone is too generic for OSM token match.
GATE_SEARCH_HINTS: dict[str, list[str]] = {
    "aksestanjungpriuk": ["tanjungpriok", "aksestanjungpriuk"],
    "seksie1e2e2a": ["tanjungpriok", "seksie"],
    "jembatantigapluit": ["jembatantiga", "pluit"],
    "pondokgedebarattimur": ["pondokgedebarat", "pondokgedetimur"],
    "gtjatiwaringin1dan2": ["jatiwaringin"],
    "gtmargajaya1dan2": ["margajaya"],
    "gtbintarajayadanjakasampurna": ["bintarajaya", "jakasampurna"],
    "gtpondokkelapa1dan2": ["pondokkelapa"],
    "jccibitung": ["cibitung", "gtcibitung"],
    "jccibitung": ["cibitung", "gtcibitung"],
    "junctioncimanggis": ["cimanggis"],
    "sscimanggis": ["cimanggis"],
    "on/offrampjatikarya": ["jatikarya"],
    "sssetuselatan": ["setuselatan"],
    "sssetuutara": ["setuutara"],
    "ssnarogong": ["narogong"],
    "sslegok": ["legok"],
    "sscbd": ["cbd", "serpongcbd"],
    "sscikeas": ["cikeas"],
    "simpangsusuncikeas": ["cikeas"],
    "jckunciran": ["kunciran"],
    "jcserpong": ["serpong"],
    "junctionserpong": ["serpong"],
    "jakarta": ["jakartadalamkota", "halim", "cawang"],
    "jakartaic": ["jakartadalamkota", "cawang"],
    "jakartadalamkota": ["jakartadalamkota", "cawang"],
    "kebonbawang": ["kebonbawang", "kebonnanas"],
    "penjaringan": ["penjaringan", "pluit"],
    "ulujami": ["ulujami", "pondokaren"],
    "pulogebang": ["pulogebang", "cakung"],
    "kelapagading": ["kelapagading"],
    "simpangsemplak": ["semplak", "sentul"],
    "cinere": ["cinere", "limo"],
    "cilincing": ["cilincing"],
    "casablanca": ["casablanca", "cawang"],
    "dawuan": ["dawuan"],
    "profdrsoedijatmo": ["soedijatmo", "sedyatmo"],
    "profdrirsoedijatmo": ["soedijatmo", "sedyatmo"],
}

_nominatim_last = 0.0


def fetch_osm_rows() -> list[dict]:
    query = """
[out:json][timeout:120];
(
  node["barrier"="toll_booth"](-6.85,106.35,-5.95,107.55);
  node["highway"="toll_gantry"](-6.85,106.35,-5.95,107.55);
);
out body;
"""
    req = urllib.request.Request(
        OVERPASS_URL,
        data=query.encode(),
        method="POST",
        headers={"User-Agent": "uang-pengiriman-geocode/1.0"},
    )
    data = json.load(urllib.request.urlopen(req, timeout=120))
    rows = []
    for el in data.get("elements", []):
        if el.get("lat") is None:
            continue
        name = (el.get("tags") or {}).get("name") or ""
        if not name:
            continue
        rows.append(
            {
                "name": name.strip(),
                "latitude": float(el["lat"]),
                "longitude": float(el["lon"]),
                "norm": _normalize_gate_name(name),
            }
        )
    return rows


def load_gate_names() -> list[str]:
    names: set[str] = set()
    for path in (DATA_DIR / "bpjt_jabodetabek_gates.json", DATA_DIR / "bpjt_trans_jawa_japek.json"):
        if not path.exists():
            continue
        pack = json.loads(path.read_text(encoding="utf-8"))
        for matrix in pack.get("matrices", []):
            for fare in matrix.get("fares", []):
                for key in ("entry", "exit"):
                    gate = (fare.get(key) or "").strip()
                    if gate:
                        names.add(gate)
    return sorted(names)


def _tokens(name: str) -> set[str]:
    norm = _normalize_gate_name(name)
    norm = re.sub(r"\d+", "", norm)
    return {t for t in re.findall(r"[a-z]{3,}", norm)}


def _hint_tokens(gate_name: str) -> set[str]:
    key = _normalize_gate_name(gate_name)
    hints = GATE_SEARCH_HINTS.get(key, [])
    tokens = set()
    for hint in hints:
        tokens |= _tokens(hint)
    if not tokens:
        tokens = _tokens(gate_name)
    return tokens


def score_match(gate_name: str, osm_name: str) -> float:
    gate_norm = _normalize_gate_name(gate_name)
    osm_norm = _normalize_gate_name(osm_name)
    if not gate_norm or not osm_norm:
        return -1.0
    if gate_norm == osm_norm:
        return 100.0
    if gate_norm in osm_norm:
        return 88.0
    if osm_norm in gate_norm:
        return 78.0

    gate_tokens = _hint_tokens(gate_name)
    osm_tokens = _tokens(osm_name)
    if not gate_tokens:
        return -1.0
    overlap = gate_tokens & osm_tokens
    if not overlap:
        return -1.0
    score = (len(overlap) / len(gate_tokens)) * 72.0
    if "gerbangtol" in osm_norm or "tollgate" in osm_norm:
        score += 8.0
    return score


def pick_best_osm(gate_name: str, osm_rows: list[dict]) -> dict | None:
    best = None
    best_score = 0.0
    for row in osm_rows:
        s = score_match(gate_name, row["name"])
        if s > best_score:
            best_score = s
            best = {**row, "score": s}
    if best and best_score >= 45.0:
        return best
    return None


def nominatim_search(query: str) -> tuple[float, float] | None:
    global _nominatim_last
    elapsed = time.time() - _nominatim_last
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _nominatim_last = time.time()

    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 5, "countrycodes": "id"}
    )
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": "uang-pengiriman-geocode/1.0"},
    )
    data = json.load(urllib.request.urlopen(req, timeout=60))
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    try:
        return float(first["lat"]), float(first["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def resolve_coords(gate_name: str, osm_rows: list[dict]) -> tuple[float, float, str] | None:
    osm = pick_best_osm(gate_name, osm_rows)
    if osm:
        return osm["latitude"], osm["longitude"], f"osm:{osm['name']}"

    queries = [
        f"Gerbang Tol {gate_name}, Jabodetabek, Indonesia",
        f"Toll Gate {gate_name}, Jakarta, Indonesia",
        f"{gate_name} gerbang tol Indonesia",
    ]
    for query in queries:
        coords = nominatim_search(query)
        if coords:
            return coords[0], coords[1], f"nominatim:{query[:48]}"
    return None


def build_mapping(osm_rows: list[dict]) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    unmatched: list[str] = []
    for gate_name in load_gate_names():
        resolved = resolve_coords(gate_name, osm_rows)
        key = _normalize_gate_name(gate_name)
        if not resolved:
            unmatched.append(gate_name)
            continue
        lat, lng, source = resolved
        mapping[key] = {
            "name": gate_name,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "source": source,
        }
        print(f"OK  {gate_name:35} ({lat:.6f}, {lng:.6f}) [{source}]")

    print(f"\nResolved {len(mapping)}/{len(mapping) + len(unmatched)}")
    if unmatched:
        print("Unresolved:")
        for name in unmatched:
            print(f"  - {name}")
    return mapping


def apply_to_db(mapping: dict[str, dict], dry_run: bool = False) -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.models import TollGate

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    gates = db.scalars(select(TollGate)).all()

    updated = 0
    missing = 0
    for gate in gates:
        key = _normalize_gate_name(gate.name)
        row = mapping.get(key)
        if not row:
            missing += 1
            print(f"SKIP {gate.name} (no mapping)")
            continue
        old = (gate.latitude, gate.longitude)
        new = (row["latitude"], row["longitude"])
        print(f"{'DRY' if dry_run else 'SET'} {gate.name}: {old} -> {new}")
        if not dry_run:
            gate.latitude = new[0]
            gate.longitude = new[1]
        updated += 1

    if not dry_run:
        db.commit()
    print(f"\n{'Would update' if dry_run else 'Updated'} {updated} gates, {missing} without mapping")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    apply_db = "--apply-db" in sys.argv
    osm_only = "--osm-only" in sys.argv

    print("Fetching OSM toll booths...")
    osm_rows = fetch_osm_rows()
    print(f"OSM rows: {len(osm_rows)}")

    mapping = build_mapping(osm_rows)
    OUT_FILE.write_text(
        json.dumps(
            {
                "source": "OpenStreetMap toll booths + Nominatim fallback",
                "updated_at": time.strftime("%Y-%m-%d"),
                "gates": mapping,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_FILE} ({len(mapping)} gates)")

    if apply_db:
        apply_to_db(mapping, dry_run=dry_run)


if __name__ == "__main__":
    main()
