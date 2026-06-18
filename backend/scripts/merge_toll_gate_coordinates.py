"""Fill missing toll gate coordinates via Nominatim and merge into dataset."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.toll_gate_service import _normalize_gate_name

DATA_DIR = backend_dir / "data"
OSM_PARTIAL = DATA_DIR / "toll_gate_coordinates_osm.json"
OUT_FILE = DATA_DIR / "toll_gate_coordinates.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

MANUAL: dict[str, tuple[float, float, str]] = {
    "kebonbawang": (-6.155421, 106.798312, "manual:JORR Kebon Bawang"),
    "penjaringan": (-6.118312, 106.805104, "manual:JORR Penjaringan"),
    "ulujami": (-6.288012, 106.738012, "manual:JORR Ulujami"),
    "pulogebang": (-6.187220, 106.938324, "manual:Cakung/Pulogebang"),
    "kelapagading": (-6.155722, 106.896925, "manual:Kelapa Gading"),
    "cinere": (-6.334850, 106.783120, "manual:Cinere toll"),
    "cilincing": (-6.108019, 106.991022, "manual:Cilincing area"),
    "casablanca": (-6.243306, 106.859717, "manual:Casablanca/Cawang"),
    "dawuan": (-6.348000, 107.412000, "manual:Japek Dawuan"),
    "simpangsemplak": (-6.564501, 106.835691, "manual:Sentul Barat/Semplak"),
    "simpangsusuncikeas": (-6.378092, 106.971369, "manual:Narogong/Cikeas"),
    "sscikeas": (-6.378092, 106.971369, "manual:SS Cikeas"),
    "ssnarogong": (-6.378092, 106.971369, "manual:SS Narogong"),
    "sslegok": (-6.316344, 106.596060, "manual:SS Legok"),
    "sscbd": (-6.221475, 106.637188, "manual:Serpong CBD"),
    "sscimanggis": (-6.421048, 106.893678, "manual:Toll Gate Cimanggis"),
    "junctioncimanggis": (-6.421048, 106.893678, "manual:Junction Cimanggis"),
    "jccibitung": (-6.287646, 107.083119, "manual:GT Cibitung 5"),
    "jccibitung": (-6.287646, 107.083119, "manual:GT Cibitung 5"),
    "jckunciran": (-6.220309, 106.666972, "manual:Kunciran 1"),
    "jcserpong": (-6.300385, 106.705376, "manual:Serpong 1"),
    "junctionserpong": (-6.300385, 106.705376, "manual:Junction Serpong"),
    "jakarta": (-6.243306, 106.859717, "manual:Jakarta/Cawang"),
    "jakartaic": (-6.243306, 106.859717, "manual:Jakarta IC"),
    "jakartadalamkota": (-6.243306, 106.859717, "manual:Jakarta Dalam Kota"),
    "jembatantigapluit": (-6.132580, 106.791349, "manual:Jembatan Tiga 1"),
    "aksestanjungpriuk": (-6.132802, 106.892896, "manual:Tanjung Priok 1"),
    "seksie1e2e2a": (-6.132802, 106.892896, "manual:Tanjung Priok seksi"),
    "pondokgedebarattimur": (-6.256337, 106.908136, "manual:Pondok Gede Barat 2"),
    "gtjatiwaringin1dan2": (-6.245462, 106.903752, "manual:Jatiwaringin 1"),
    "gtmargajaya1dan2": (-6.249690, 106.950163, "manual:Bintara/Marga Jaya"),
    "gtbintarajayadanjakasampurna": (-6.249690, 106.950163, "manual:Bintara Jaya"),
    "gtpondokkelapa1dan2": (-6.248684, 106.933527, "manual:Pondok Kelapa 1"),
    "onofframpjatikarya": (-6.385131, 106.895567, "manual:Cimanggis/Jatikarya"),
    "sssetuselatan": (-6.312219, 106.910376, "manual:Setu Selatan"),
    "sssetuutara": (-6.312219, 106.910376, "manual:Setu Utara"),
    "profdrsoedijatmo": (-6.126000, 106.655000, "manual:Prof Soedijatmo"),
    "profdrirsoedijatmo": (-6.126000, 106.655000, "manual:Prof Soedijatmo"),
}

_nominatim_last = 0.0


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


def nominatim_search(query: str) -> tuple[float, float] | None:
    global _nominatim_last
    elapsed = time.time() - _nominatim_last
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _nominatim_last = time.time()
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 5, "countrycodes": "id"})
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": "uang-pengiriman-geocode/1.0"},
    )
    data = json.load(urllib.request.urlopen(req, timeout=60))
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    return float(first["lat"]), float(first["lon"])


def main() -> None:
    osm_map = json.loads(OSM_PARTIAL.read_text(encoding="utf-8")) if OSM_PARTIAL.exists() else {}
    gates: dict[str, dict] = {}

    for key, row in osm_map.items():
        gates[key] = {
            "name": row["name"],
            "latitude": round(float(row["latitude"]), 6),
            "longitude": round(float(row["longitude"]), 6),
            "source": f"osm:{row.get('osm_name', row['name'])}",
        }

    for key, (lat, lng, source) in MANUAL.items():
        if key not in gates:
            gates[key] = {
                "name": key,
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "source": source,
            }

    unresolved = []
    for gate_name in load_gate_names():
        key = _normalize_gate_name(gate_name)
        if key in gates:
            gates[key]["name"] = gate_name
            continue
        coords = None
        source = None
        for query in (
            f"Gerbang Tol {gate_name}, Jabodetabek, Indonesia",
            f"Toll Gate {gate_name}, Jakarta, Indonesia",
        ):
            coords = nominatim_search(query)
            if coords:
                source = f"nominatim:{query[:48]}"
                break
        if coords:
            gates[key] = {
                "name": gate_name,
                "latitude": round(coords[0], 6),
                "longitude": round(coords[1], 6),
                "source": source,
            }
            print(f"NOM {gate_name} -> {coords}")
        else:
            unresolved.append(gate_name)

    OUT_FILE.write_text(
        json.dumps(
            {
                "source": "OpenStreetMap + manual overrides + Nominatim",
                "updated_at": time.strftime("%Y-%m-%d"),
                "gates": gates,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(gates)} gates -> {OUT_FILE}")
    if unresolved:
        print("Still unresolved:", unresolved)


if __name__ == "__main__":
    main()
