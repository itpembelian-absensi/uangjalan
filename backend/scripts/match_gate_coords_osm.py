"""Match master gerbang names to OSM toll booth coordinates."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.toll_gate_service import _normalize_gate_name

DATA_DIR = backend_dir / "data"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def load_gate_names() -> list[tuple[str, str]]:
    names: dict[str, set[str]] = {}
    for path in (DATA_DIR / "bpjt_jabodetabek_gates.json", DATA_DIR / "bpjt_trans_jawa_japek.json"):
        if not path.exists():
            continue
        pack = json.loads(path.read_text(encoding="utf-8"))
        for matrix in pack.get("matrices", []):
            section = matrix.get("section_name", "")
            for fare in matrix.get("fares", []):
                for key in ("entry", "exit"):
                    gate = (fare.get(key) or "").strip()
                    if gate:
                        names.setdefault(gate, set()).add(section)

    return sorted((gate, ", ".join(sorted(sections))) for gate, sections in names.items())


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
        headers={"User-Agent": "uang-pengiriman/1.0"},
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


def _tokens(name: str) -> set[str]:
    norm = _normalize_gate_name(name)
    norm = re.sub(r"\d+", "", norm)
    return {t for t in re.findall(r"[a-z]{3,}", norm)}


def score_match(gate_name: str, osm_name: str) -> float:
    gate_norm = _normalize_gate_name(gate_name)
    osm_norm = _normalize_gate_name(osm_name)
    if not gate_norm or not osm_norm:
        return -1.0
    if gate_norm == osm_norm:
        return 100.0
    if gate_norm in osm_norm:
        return 85.0
    if osm_norm in gate_norm:
        return 75.0

    gate_tokens = _tokens(gate_name)
    osm_tokens = _tokens(osm_name)
    if not gate_tokens:
        return -1.0
    overlap = gate_tokens & osm_tokens
    if not overlap:
        return -1.0
    score = (len(overlap) / len(gate_tokens)) * 70.0
    if "gerbangtol" in osm_norm or "tollgate" in osm_norm:
        score += 8.0
    return score


def pick_best(gate_name: str, osm_rows: list[dict]) -> dict | None:
    best = None
    best_score = 0.0
    for row in osm_rows:
        s = score_match(gate_name, row["name"])
        if s > best_score:
            best_score = s
            best = {**row, "score": s}
    if best and best_score >= 40.0:
        return best
    return None


def main() -> None:
    gates = load_gate_names()
    osm_rows = fetch_osm_rows()
    print(f"Gates: {len(gates)}, OSM rows: {len(osm_rows)}")

    matched = 0
    unmatched = []
    mapping: dict[str, dict] = {}

    for gate_name, sections in gates:
        best = pick_best(gate_name, osm_rows)
        if best:
            matched += 1
            key = _normalize_gate_name(gate_name)
            mapping[key] = {
                "name": gate_name,
                "latitude": best["latitude"],
                "longitude": best["longitude"],
                "osm_name": best["name"],
                "score": best["score"],
                "sections": sections,
            }
            print(f"OK  {gate_name:35} -> {best['name']} ({best['latitude']:.6f}, {best['longitude']:.6f}) score={best['score']:.1f}")
        else:
            unmatched.append(gate_name)
            print(f"MISS {gate_name}")

    out = DATA_DIR / "toll_gate_coordinates_osm.json"
    out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMatched {matched}/{len(gates)} -> {out}")
    if unmatched:
        print(f"Unmatched ({len(unmatched)}):")
        for name in unmatched:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
