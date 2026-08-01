from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select

TOLL_NOTE_BPJT = (
    "Tarif berdasarkan ruas tol yang dilalui di peta (rute OSRM), dicocokkan ke master gerbang BPJT. "
    "Total pulang-pergi dikali 2."
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_GATE_COORDS_FILE = _DATA_DIR / "toll_gate_coordinates.json"

# Fallback jika file koordinat belum ada (mis. development lokal).
_LEGACY_GATE_COORDINATES: dict[str, tuple[float, float]] = {
    "pondokpinang": (-6.272000, 106.800000),
    "tamanmini": (-6.287103, 106.878255),
    "ulujami": (-6.239000, 106.764000),
    "rorotan": (-6.146076, 106.940282),
    "kebonbawang": (-6.155421, 106.798312),
    "kebonjeruk": (-6.190284, 106.767997),
    "penjaringan": (-6.118312, 106.805104),
    "cawang": (-6.243306, 106.859717),
    "tomang": (-6.181638, 106.793521),
    "pluit": (-6.124615, 106.779890),
    "jembatantigapluit": (-6.132580, 106.791349),
    "cikampek": (-6.439909, 107.476867),
    "cibubur": (-6.365784, 106.895049),
    "bogor": (-6.597505, 106.817689),
    "ciawi": (-6.631068, 106.839146),
    "padalarang": (-6.834167, 107.472222),
    "cileunyi": (-6.944722, 107.638889),
    "pasteur": (-6.887500, 107.583333),
    "cikopo": (-6.474000, 107.477000),
    "cisumdawuutama": (-7.037000, 107.857000),
    "paseh": (-7.102000, 107.812000),
}


@lru_cache(maxsize=1)
def _load_gate_coordinates() -> dict[str, tuple[float, float]]:
    coords = dict(_LEGACY_GATE_COORDINATES)
    if not _GATE_COORDS_FILE.exists():
        return coords
    try:
        payload = json.loads(_GATE_COORDS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return coords
    for key, row in (payload.get("gates") or {}).items():
        try:
            coords[key] = (float(row["latitude"]), float(row["longitude"]))
        except (KeyError, TypeError, ValueError):
            continue
    return coords


# Koordinat acuan gerbang — dipakai jika belum diisi di database.
BUILTIN_GATE_COORDINATES: dict[str, tuple[float, float]] = _load_gate_coordinates()

# (kata kunci di nama ruas tol OSRM, kata kunci di nama ruas/gerbang BPJT)
SECTION_ROUTE_HINTS: list[tuple[list[str], list[str]]] = [
    (["sedyatmo", "soedijatmo"], ["sedyatmo", "soedijatmo"]),
    (["pelabuhan", "priok", "tanjungpriuk"], ["priok", "pelabuhan", "tanjungpriuk", "aksestanjung"]),
    (["ancol", "jembatantiga", "pluit"], ["ancol", "pluit", "jembatantiga", "priok", "cawang"]),
    (["cawang", "tomang", "dalamkota", "cawangpluit"], ["cawang", "ctc", "tomang", "dalamkota", "pluit"]),
    (["cikampek", "japek"], ["cikampek", "japek"]),
    (["bekasi", "cikarang", "karawang", "tambun", "cibitung"], ["cikampek", "japek", "bekasi", "cikarang", "karawang", "tambun"]),
    (["jorr", "lingkarluar", "outer", "kayubesar", "jatiasih"], ["jorr", "lingkarluar", "kayubesar", "jatiasih", "cikunir", "cilincing", "kebonbawang"]),
    (["bogor", "ciawi", "jagorawi", "cinere"], ["bogor", "ciawi", "jagorawi", "cinere"]),
    (["kelapagading", "pulogebang"], ["dalamkota", "kelapagading", "pulogebang"]),
    (["cengkareng", "batuceper"], ["cengkareng", "batuceper", "benda"]),
    (["kunciran", "serpong"], ["kunciran", "serpong"]),
    (["kamal", "balaraja"], ["balaraja", "serpong", "kamal"]),
    (["jakartabogor", "jagorawi"], ["bogor", "ciawi", "jagorawi", "jakartabogor"]),
    (["lingkardalam", "inner"], ["dalamkota", "ctc", "lingkardalam"]),
    (["tomang", "cawangpluit"], ["cawang", "ctc", "tomang", "pluit", "dalamkota"]),
    (["cinere"], ["cinere", "jagorawi", "cimanggis"]),
    (["bekasicawang", "bckm"], ["bekasi", "cawang", "kampungmelayu"]),
    (["cimanggis", "cibitung"], ["cimanggis", "cibitung", "jatikarya"]),
    (["merak", "tangerang", "karawaci", "bitung", "cikupa"], ["merak", "tangerang", "karawaci", "bitung", "cikupa"]),
    (["bocimi", "cibadak", "cigombong", "caringin", "parungkuda", "sukabumi"], ["bocimi", "cibadak", "cigombong", "caringin", "parungkuda", "ciawi"]),
    (["cipularang", "purwakarta", "padalarang"], ["cipularang", "padalarang", "purwakarta"]),
    (["padaleunyi", "purbaleunyi", "padalarangcileunyi"], ["padaleunyi", "purbaleunyi", "cileunyi", "pasteur"]),
    (["cisumdawu", "sumedang"], ["cisumdawu", "sumedang", "jatinangor", "paseh"]),
    (["cipali", "cikopo", "palimanan"], ["cipali", "cikopo", "palimanan"]),
    (["bakauheni", "terbanggi", "sumatera"], ["bakauheni", "terbanggi", "sumatera"]),
    (["ferry", "penyeberangan", "kapal"], ["ferry", "penyeberangan", "merakbakauheni"]),
]


def _road_matches_bpjt_section(
    road_name: str, section_name: str, gate_names: list[str] | None = None
) -> bool:
    road_norm = _normalize_toll_text(road_name)
    section_norm = _normalize_toll_text(section_name)
    section_text = _section_text(section_name, [{"name": n} for n in (gate_names or [])])

    if section_norm and len(section_norm) >= 8 and section_norm in road_norm:
        return True
    if road_norm and len(road_norm) >= 8 and road_norm in section_norm:
        return True

    for road_hints, section_hints in SECTION_ROUTE_HINTS:
        if any(h in road_norm for h in road_hints) and any(h in section_text for h in section_hints):
            return True
    return False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _normalize_toll_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _normalize_gate_name(name: str) -> str:
    return _normalize_toll_text(name)


def _gate_coordinates(gate: dict) -> tuple[float, float] | None:
    glat = gate.get("latitude")
    glng = gate.get("longitude")
    if glat is not None and glng is not None:
        return float(glat), float(glng)
    key = _normalize_gate_name(gate.get("name") or "")
    return _load_gate_coordinates().get(key)


def _fare_index(fares: list[dict]) -> dict[tuple[int, int, str], float]:
    index: dict[tuple[int, int, str], float] = {}
    for row in fares:
        key = (row["entry_gate_id"], row["exit_gate_id"], row["golongan_code"])
        index[key] = float(row["rate"])
    return index


def _resolve_gate_rate(
    index: dict[tuple[int, int, str], float],
    entry_id: int,
    exit_id: int,
    golongan_code: str,
) -> float | None:
    gol = (golongan_code or "II").strip().upper()
    rate = index.get((entry_id, exit_id, gol))
    if rate is None and gol in ("III",):
        rate = index.get((entry_id, exit_id, "II"))
    if rate is None or rate <= 0:
        return None
    return float(rate)


def _rates_all_golongan(
    index: dict[tuple[int, int, str], float],
    entry_id: int,
    exit_id: int,
) -> dict[str, float]:
    rates: dict[str, float] = {}
    for gol in ("I", "II", "III", "IV", "V"):
        rate = _resolve_gate_rate(index, entry_id, exit_id, gol)
        if rate is not None:
            rates[gol] = rate
    return rates


def _section_rates_by_code(section: dict, golongan_code: str) -> dict[str, float]:
    by_code = section.get("rates_by_code") or {}
    if by_code:
        return {str(k): float(v) for k, v in by_code.items()}
    gol23 = float(section.get("gol23") or 0)
    gol45 = float(section.get("gol45") or 0)
    rates: dict[str, float] = {}
    if gol23 > 0:
        rates["II"] = gol23
        rates["III"] = gol23
    if gol45 > 0:
        rates["IV"] = gol45
        rates["V"] = gol45
    return rates


def _section_rate_for_golongan(section: dict, golongan_code: str) -> float:
    rates = _section_rates_by_code(section, golongan_code)
    gol = (golongan_code or "II").strip().upper()
    if gol in rates:
        return rates[gol]
    if gol in ("II", "III"):
        return rates.get("II", rates.get("III", 0.0))
    return rates.get("IV", rates.get("V", 0.0))


def _route_toll_text(route_toll_roads: list[str] | None) -> str:
    return _normalize_toll_text(" ".join(route_toll_roads or []))


def _section_text(section_name: str, section_gates: list[dict]) -> str:
    gate_names = " ".join(g.get("name") or "" for g in section_gates)
    return _normalize_toll_text(f"{section_name} {gate_names}")


def _section_matches_route(
    section_name: str,
    section_gates: list[dict],
    route_toll_roads: list[str] | None,
    dest_lat: float,
    dest_lng: float,
) -> bool:
    if not route_toll_roads:
        return True

    route_text = _route_toll_text(route_toll_roads)
    section_text = _section_text(section_name, section_gates)

    for road_hints, section_hints in SECTION_ROUTE_HINTS:
        route_hit = any(h in route_text for h in road_hints)
        section_hit = any(h in section_text for h in section_hints)
        if route_hit and section_hit:
            return True

    # Destinasi timur (Bekasi/Cikarang): izinkan Japek walau OSRM hanya sebut Sedyatmo/Pelabuhan
    east_dest = dest_lng > 106.94 and -6.35 < dest_lat < -6.15
    if east_dest and any(h in section_text for h in ["cikampek", "japek", "bekasi", "cikarang"]):
        return True

    return False


def _is_flat_section(section: dict | None) -> bool:
    if not section:
        return False
    origin = _normalize_toll_text(section.get("origin_name") or "")
    destination = _normalize_toll_text(section.get("destination_name") or "")
    return bool(origin and origin == destination)


def _find_section_meta(sections: list[dict], section_name: str) -> dict | None:
    target = _normalize_toll_text(section_name)
    for sec in sections:
        if _normalize_toll_text(sec.get("name") or "") == target:
            return sec
    return None


def _section_fare_pairs(
    section_gates: list[dict],
    index: dict[tuple[int, int, str], float],
) -> list[dict]:
    gate_ids = {g["id"] for g in section_gates}
    gate_by_id = {g["id"]: g for g in section_gates}
    pairs: list[dict] = []
    seen: set[tuple[int, int]] = set()

    for (entry_id, exit_id, gol), rate in index.items():
        if gol != "II":
            continue
        if entry_id not in gate_ids or exit_id not in gate_ids or entry_id == exit_id:
            continue
        key = (entry_id, exit_id)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(
            {
                "entry": gate_by_id[entry_id],
                "exit": gate_by_id[exit_id],
                "rate_ii": float(rate),
            }
        )

    return pairs


def _normalize_route_toll_items(
    route_toll_roads: list[str] | list[dict] | None,
) -> list[dict]:
    items: list[dict] = []
    for raw in route_toll_roads or []:
        if isinstance(raw, dict):
            name = (raw.get("name") or "").strip()
            if not name:
                continue
            items.append(
                {
                    "name": name,
                    "latitude": raw.get("latitude"),
                    "longitude": raw.get("longitude"),
                    "geometry": raw.get("geometry") or [],
                }
            )
        else:
            name = str(raw or "").strip()
            if name:
                items.append({"name": name, "latitude": None, "longitude": None, "geometry": []})
    return items


def _toll_item_endpoints(
    item: dict,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    geom = item.get("geometry") or []
    if len(geom) >= 2:
        start = (float(geom[0][0]), float(geom[0][1]))
        end = (float(geom[-1][0]), float(geom[-1][1]))
        return start, end
    lat = item.get("latitude")
    lng = item.get("longitude")
    if lat is not None and lng is not None:
        pt = (float(lat), float(lng))
        return pt, pt
    return (origin_lat, origin_lng), (dest_lat, dest_lng)


def _road_section_match_score(road_name: str, section: dict) -> float:
    road_norm = _normalize_toll_text(road_name)
    sec_name = section.get("name") or ""
    section_norm = _normalize_toll_text(sec_name)
    section_text = _section_text(sec_name, [])

    if not _road_matches_bpjt_section(road_name, sec_name, []):
        return 0.0

    score = 0.0
    if section_norm and len(section_norm) >= 8 and section_norm in road_norm:
        score += 120 + len(section_norm)
    if road_norm and len(road_norm) >= 8 and road_norm in section_norm:
        score += 100 + len(road_norm)

    for road_hints, section_hints in SECTION_ROUTE_HINTS:
        road_hits = sum(1 for h in road_hints if h in road_norm)
        sec_hits = sum(1 for h in section_hints if h in section_text or h in section_norm)
        if road_hits and sec_hits:
            score += road_hits * 12 + sec_hits * 6

    if "cawang" in road_norm and "pluit" in road_norm and "kelapagading" not in road_norm:
        if "ctc" in section_norm or "cawangtomang" in section_norm:
            score += 60
        if "kelapagading" in section_norm or "pulogebang" in section_norm:
            score -= 40

    if "dalamkota" in road_norm and "kelapagading" not in road_norm and "pulogebang" not in road_norm:
        if "dalamkota" in section_norm and "kelapagading" in section_norm:
            score += 25

    return score


def _find_section_for_road(road_name: str, sections: list[dict]) -> dict | None:
    scored = [
        (sec, _road_section_match_score(road_name, sec))
        for sec in sections
    ]
    scored = [(sec, pts) for sec, pts in scored if pts > 0]
    if not scored:
        return None
    return max(scored, key=lambda item: item[1])[0]


def _segment_dedup_key(segment: dict) -> str:
    sid = segment.get("section_id")
    if sid is not None:
        return f"sid:{sid}"
    entry = _normalize_gate_name(
        segment.get("entry_gate_name") or segment.get("entry_gate_code") or ""
    )
    exit_key = _normalize_gate_name(
        segment.get("exit_gate_name") or segment.get("exit_gate_code") or ""
    )
    if entry and exit_key:
        return f"gate:{entry}:{exit_key}"
    return f"name:{_normalize_toll_text(segment.get('section_name') or '')}"


def _dedupe_toll_segments(segments: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for segment in segments:
        key = _segment_dedup_key(segment)
        if key in seen:
            continue
        seen.add(key)
        unique.append(segment)
    return unique


def _full_section_fare_pair(
    section_meta: dict | None,
    section_gates: list[dict],
    index: dict[tuple[int, int, str], float],
    golongan_code: str,
) -> dict | None:
    if not section_meta or not section_gates:
        return None
    origin_key = _normalize_gate_name(section_meta.get("origin_name") or "")
    dest_key = _normalize_gate_name(section_meta.get("destination_name") or "")
    if not origin_key or not dest_key or origin_key == dest_key:
        return None

    entry_gate = exit_gate = None
    for gate in section_gates:
        gate_key = _normalize_gate_name(gate.get("name") or "")
        if not gate_key:
            continue
        if entry_gate is None and (
            gate_key == origin_key or origin_key in gate_key or gate_key in origin_key
        ):
            entry_gate = gate
        if exit_gate is None and (
            gate_key == dest_key or dest_key in gate_key or gate_key in dest_key
        ):
            exit_gate = gate

    if not entry_gate or not exit_gate or entry_gate["id"] == exit_gate["id"]:
        return None

    rate = _resolve_gate_rate(index, entry_gate["id"], exit_gate["id"], golongan_code)
    if rate is None:
        return None
    return {"entry": entry_gate, "exit": exit_gate, "rate": rate}


def _best_fare_pair_for_section(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    section_gates: list[dict],
    index: dict[tuple[int, int, str], float],
    *,
    max_exit_km: float | None = 18.0,
) -> dict | None:
    pairs = _section_fare_pairs(section_gates, index)
    if not pairs:
        return None

    best: dict | None = None
    best_score = float("inf")

    for pair in pairs:
        entry_coords = _gate_coordinates(pair["entry"])
        exit_coords = _gate_coordinates(pair["exit"])
        if not entry_coords or not exit_coords:
            continue

        entry_dist = haversine_km(origin_lat, origin_lng, entry_coords[0], entry_coords[1])
        exit_dist = haversine_km(dest_lat, dest_lng, exit_coords[0], exit_coords[1])
        if max_exit_km is not None and exit_dist > max_exit_km:
            continue

        score = entry_dist + exit_dist
        if score < best_score:
            best_score = score
            best = {
                **pair,
                "_entry_distance_km": entry_dist,
                "_exit_distance_km": exit_dist,
            }

    return best


def _section_route_label(section: dict) -> str:
    origin = (section.get("origin_name") or "").strip()
    dest = (section.get("destination_name") or "").strip()
    if origin and dest:
        if _normalize_gate_name(origin) == _normalize_gate_name(dest):
            return origin
        return f"{origin} → {dest}"
    if origin:
        return origin
    return (section.get("name") or "Ruas tol").strip()


def _build_route_section_fallback(
    road_name: str, section: dict, golongan_code: str
) -> dict | None:
    rate = _section_rate_for_golongan(section, golongan_code)
    if rate <= 0:
        return None
    sec_name = section.get("name") or road_name
    return {
        "source": "route",
        "section_name": road_name,
        "entry_gate_code": None,
        "entry_gate_name": section.get("origin_name"),
        "exit_gate_code": None,
        "exit_gate_name": section.get("destination_name"),
        "detail": f"Dari rute peta · acuan {sec_name}",
        "weight_pct": None,
        "one_way_idr": rate,
        "round_trip_idr": rate * 2,
        "rates_by_golongan": _section_rates_by_code(section, golongan_code),
    }


def _build_segment(
    entry: dict,
    exit_gate: dict,
    section_name: str,
    index: dict[tuple[int, int, str], float],
    one_way_rate: float,
    *,
    rates_by_golongan: dict[str, float] | None = None,
) -> dict:
    entry_label = entry.get("code") or entry.get("name") or "Gerbang masuk"
    exit_label = exit_gate.get("code") or exit_gate.get("name") or "Gerbang keluar"
    if rates_by_golongan is None:
        rates_by_golongan = _rates_all_golongan(index, entry["id"], exit_gate["id"])
    return {
        "source": "gate",
        "section_name": section_name,
        "entry_gate_code": entry.get("code"),
        "entry_gate_name": entry.get("name"),
        "exit_gate_code": exit_gate.get("code"),
        "exit_gate_name": exit_gate.get("name"),
        "detail": f"{entry_label} → {exit_label}",
        "weight_pct": None,
        "one_way_idr": one_way_rate,
        "round_trip_idr": one_way_rate * 2,
        "rates_by_golongan": rates_by_golongan,
    }


def _build_flat_segment(section: dict, golongan_code: str) -> dict | None:
    rate = _section_rate_for_golongan(section, golongan_code)
    if rate <= 0:
        return None
    name = section.get("name") or "Ruas tol"
    rates_by_golongan = _section_rates_by_code(section, golongan_code)
    return {
        "source": "gate",
        "section_name": name,
        "entry_gate_code": None,
        "entry_gate_name": section.get("origin_name") or name,
        "exit_gate_code": None,
        "exit_gate_name": section.get("destination_name") or name,
        "detail": f"Tarif ruas {name}",
        "weight_pct": None,
        "one_way_idr": rate,
        "round_trip_idr": rate * 2,
        "rates_by_golongan": rates_by_golongan,
    }


def _apply_route_segment_labels(segment: dict, road_name: str) -> dict:
    segment = dict(segment)
    segment["section_name"] = road_name
    segment["source"] = "route"
    base_detail = segment.get("detail") or road_name
    segment["detail"] = f"Dari rute peta · {base_detail}"
    return segment


def _finalize_route_segments(
    segments: list[dict],
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> list[dict]:
    if not segments:
        return segments

    trip_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    north_dest = dest_lng < 106.93 and dest_lat > -6.25
    east_dest = dest_lng > 106.94 and -6.35 < dest_lat < -6.15
    gate_segments = [s for s in segments if s.get("exit_gate_code")]
    flat_segments = [s for s in segments if s not in gate_segments]

    if east_dest and gate_segments:
        return gate_segments
    if north_dest and flat_segments and trip_km < 35:
        return flat_segments
    if north_dest and flat_segments and gate_segments:
        ancol_exits = [
            s
            for s in gate_segments
            if any(
                k in _normalize_toll_text(s.get("exit_gate_name") or "")
                for k in ["ancol", "pluit", "jembatantiga", "priok", "penjaringan"]
            )
        ]
        if ancol_exits:
            return flat_segments + [min(ancol_exits, key=lambda s: s["one_way_idr"])]
        return flat_segments
    return segments


def _segment_for_map_road(
    item: dict,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    sections: list[dict],
    by_section: dict[int, list[dict]],
    index: dict[tuple[int, int, str], float],
    golongan_code: str,
) -> dict | None:
    """Satu baris tarif untuk satu ruas tol dari peta — selalu coba gate, lalu acuan ruas."""
    road_name = item["name"]
    seg_start, seg_end = _toll_item_endpoints(item, origin_lat, origin_lng, dest_lat, dest_lng)
    start_lat, start_lng = seg_start
    end_lat, end_lng = seg_end

    section_meta = _find_section_for_road(road_name, sections)
    if section_meta and _is_flat_section(section_meta):
        flat_segment = _build_flat_segment(section_meta, golongan_code)
        if flat_segment:
            seg = _apply_route_segment_labels(flat_segment, road_name)
            seg["section_id"] = section_meta.get("id")
            return seg

    section_gates: list[dict] = []
    if section_meta:
        target = _normalize_toll_text(section_meta.get("name") or "")
        for gates in by_section.values():
            gate_section = _normalize_toll_text(gates[0].get("section_name") or "")
            if gate_section == target:
                section_gates = gates
                break

    if section_gates:
        # Use the toll road segment geometry endpoints for gate matching,
        # not the overall trip origin/destination. This is crucial for ring
        # roads (JORR) where the trip endpoints can be far from where the
        # vehicle actually enters/exits the toll road.
        picked = _best_fare_pair_for_section(
            start_lat,
            start_lng,
            end_lat,
            end_lng,
            section_gates,
            index,
            max_exit_km=None,
        )
        if picked:
            rate = _resolve_gate_rate(
                index, picked["entry"]["id"], picked["exit"]["id"], golongan_code
            )
            if rate is not None:
                seg = _apply_route_segment_labels(
                    _build_segment(
                        picked["entry"],
                        picked["exit"],
                        section_meta.get("name") if section_meta else road_name,
                        index,
                        rate,
                    ),
                    road_name,
                )
                seg["section_id"] = section_meta.get("id") if section_meta else None
                return seg

        full_pair = _full_section_fare_pair(
            section_meta, section_gates, index, golongan_code
        )
        if full_pair:
            seg = _apply_route_segment_labels(
                _build_segment(
                    full_pair["entry"],
                    full_pair["exit"],
                    section_meta.get("name") if section_meta else road_name,
                    index,
                    full_pair["rate"],
                ),
                road_name,
            )
            seg["section_id"] = section_meta.get("id") if section_meta else None
            return seg

    if section_meta:
        fallback = _build_route_section_fallback(road_name, section_meta, golongan_code)
        if fallback:
            fallback["section_id"] = section_meta.get("id")
            return fallback

    return None


def _breakdown_from_map_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    route_toll_roads: list[str] | list[dict],
    sections: list[dict],
    by_section: dict[int, list[dict]],
    index: dict[tuple[int, int, str], float],
    golongan_code: str,
) -> list[dict]:
    """Satu baris tarif per ruas tol yang terdeteksi di garis rute peta."""
    segments: list[dict] = []
    toll_items = _normalize_route_toll_items(route_toll_roads)

    for item in toll_items:
        segment = _segment_for_map_road(
            item,
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            sections,
            by_section,
            index,
            golongan_code,
        )
        if segment:
            segments.append(segment)
            continue

        segments.append(
            {
                "source": "route",
                "section_name": item["name"],
                "entry_gate_code": None,
                "entry_gate_name": None,
                "exit_gate_code": None,
                "exit_gate_name": None,
                "detail": "Belum terpetakan ke master BPJT",
                "weight_pct": None,
                "one_way_idr": 0.0,
                "round_trip_idr": 0.0,
                "rates_by_golongan": {},
            }
        )

    return _dedupe_toll_segments(segments)


def breakdown_from_route_sections_only(
    route_toll_roads: list[str] | list[dict],
    sections: list[dict],
    golongan_code: str = "II",
) -> dict | None:
    """Fallback: tarif acuan ruas BPJT hanya untuk ruas yang muncul di rute peta."""
    toll_items = _normalize_route_toll_items(route_toll_roads)
    if not toll_items or not sections:
        return None

    segments: list[dict] = []

    for item in toll_items:
        road_name = item["name"]
        sec = _find_section_for_road(road_name, sections)
        if not sec:
            continue
        fallback = _build_route_section_fallback(road_name, sec, golongan_code)
        if fallback:
            fallback["section_id"] = sec.get("id")
            segments.append(fallback)

    segments = _dedupe_toll_segments(segments)
    if not segments:
        return None

    one_way = sum(float(s["one_way_idr"]) for s in segments)
    return {
        "one_way_idr": one_way,
        "description": "; ".join(s["detail"] for s in segments),
        "segments": segments,
    }


def estimate_toll_bpjt_breakdown(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    gates: list[dict],
    fares: list[dict],
    golongan_code: str = "II",
    *,
    distance_km: float | None = None,
    route_toll_roads: list[str] | list[dict] | None = None,
    sections: list[dict] | None = None,
) -> dict | None:
    """
    Hitung tarif tol: utamakan ruas tol yang terdeteksi di garis rute peta (OSRM).
    """
    del distance_km
    toll_items = _normalize_route_toll_items(route_toll_roads)

    if not gates or not fares:
        if toll_items and sections:
            return breakdown_from_route_sections_only(toll_items, sections, golongan_code)
        return None

    index = _fare_index(fares)
    sections = sections or []

    by_section: dict[int, list[dict]] = {}
    for gate in gates:
        if not gate.get("is_active", True):
            continue
        sid = gate["section_id"]
        by_section.setdefault(sid, []).append(gate)

    if toll_items:
        map_segments = _breakdown_from_map_route(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            toll_items,
            sections,
            by_section,
            index,
            golongan_code,
        )
        priced = [s for s in map_segments if float(s.get("one_way_idr") or 0) > 0]
        if priced:
            one_way_total = sum(float(s["one_way_idr"]) for s in priced)
            return {
                "one_way_idr": one_way_total,
                "description": "; ".join(s["detail"] for s in priced),
                "segments": map_segments,
            }
        route_only = breakdown_from_route_sections_only(
            toll_items, sections, golongan_code
        )
        if route_only:
            return route_only
        return None

    # Tanpa data rute peta: fallback ke pencocokan koordinat
    segments: list[dict] = []
    used_flat_sections: set[str] = set()

    # Ruas flat (mis. Sedyatmo) — belum punya matriks gerbang terpisah
    for sec in sections:
        if not _is_flat_section(sec):
            continue
        section_name = sec.get("name") or ""
        if not _section_matches_route(section_name, [], route_toll_roads, dest_lat, dest_lng):
            continue
        flat_key = _normalize_toll_text(section_name)
        if flat_key in used_flat_sections:
            continue
        flat_segment = _build_flat_segment(sec, golongan_code)
        if flat_segment:
            segments.append(flat_segment)
            used_flat_sections.add(flat_key)

    for section_gates in by_section.values():
        section_name = section_gates[0].get("section_name") or "Ruas tol"
        if not _section_matches_route(
            section_name, section_gates, route_toll_roads, dest_lat, dest_lng
        ):
            continue

        section_meta = _find_section_meta(sections, section_name)

        if _is_flat_section(section_meta):
            flat_key = _normalize_toll_text(section_name)
            if flat_key in used_flat_sections:
                continue
            flat_segment = _build_flat_segment(section_meta, golongan_code)
            if flat_segment:
                segments.append(flat_segment)
                used_flat_sections.add(flat_key)
            continue

        picked = _best_fare_pair_for_section(
            origin_lat, origin_lng, dest_lat, dest_lng, section_gates, index
        )
        if not picked:
            continue

        rate = _resolve_gate_rate(
            index, picked["entry"]["id"], picked["exit"]["id"], golongan_code
        )
        if rate is None:
            continue

        segments.append(
            _build_segment(
                picked["entry"], picked["exit"], section_name, index, rate
            )
        )

    if not segments:
        if route_toll_roads and sections:
            return breakdown_from_route_sections_only(route_toll_roads, sections, golongan_code)
        return None

    trip_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    north_dest = dest_lng < 106.93 and dest_lat > -6.25
    east_dest = dest_lng > 106.94 and -6.35 < dest_lat < -6.15
    gate_segments = [s for s in segments if s.get("exit_gate_code")]
    flat_segments = [s for s in segments if s not in gate_segments]

    if east_dest and gate_segments:
        segments = gate_segments
    elif north_dest and flat_segments and trip_km < 35:
        segments = flat_segments
    elif north_dest and flat_segments:
        ancol_exits = [
            s
            for s in segments
            if s not in flat_segments
            and any(
                k in _normalize_toll_text(s.get("exit_gate_name") or "")
                for k in ["ancol", "pluit", "jembatantiga", "priok", "penjaringan"]
            )
        ]
        if ancol_exits:
            segments = flat_segments + [min(ancol_exits, key=lambda s: s["one_way_idr"])]
        else:
            segments = flat_segments

    one_way_total = sum(float(s["one_way_idr"]) for s in segments)
    descriptions = [s["detail"] for s in segments]
    return {
        "one_way_idr": one_way_total,
        "description": "; ".join(descriptions),
        "segments": segments,
    }


def estimate_toll_bpjt_gates(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    gates: list[dict],
    fares: list[dict],
    golongan_code: str = "II",
    *,
    distance_km: float | None = None,
    route_toll_roads: list[str] | list[dict] | None = None,
    sections: list[dict] | None = None,
) -> tuple[float, str] | None:
    result = estimate_toll_bpjt_breakdown(
        origin_lat,
        origin_lng,
        dest_lat,
        dest_lng,
        gates,
        fares,
        golongan_code,
        distance_km=distance_km,
        route_toll_roads=route_toll_roads,
        sections=sections,
    )
    if not result:
        return None
    return result["one_way_idr"], result["description"]


def build_segment_for_master_section(
    section: dict,
    gates: list[dict],
    fares: list[dict],
    golongan_code: str = "II",
) -> dict | None:
    """Bangun satu baris tarif dari master ruas tol (pilihan manual)."""
    section_id = section.get("id")
    section_name = section.get("name") or "Ruas tol"
    route_label = _section_route_label(section)
    section_gates = [
        g for g in gates if g.get("section_id") == section_id and g.get("is_active", True)
    ]
    index = _fare_index(fares)

    if _is_flat_section(section):
        segment = _build_flat_segment(section, golongan_code)
        if segment:
            segment["source"] = "manual"
            segment["section_id"] = section_id
            segment["section_name"] = route_label
            segment["detail"] = f"Pilih manual · {segment.get('detail') or route_label}"
            return segment

    full_pair = _full_section_fare_pair(section, section_gates, index, golongan_code)
    if full_pair:
        segment = _build_segment(
            full_pair["entry"],
            full_pair["exit"],
            route_label,
            index,
            full_pair["rate"],
        )
        segment["source"] = "manual"
        segment["section_id"] = section_id
        segment["section_name"] = route_label
        segment["detail"] = (
            f"Pilih manual · {segment.get('entry_gate_name') or ''} → "
            f"{segment.get('exit_gate_name') or ''}"
        ).strip(" · →")
        return segment

    fallback = _build_route_section_fallback(route_label, section, golongan_code)
    if fallback:
        fallback["source"] = "manual"
        fallback["section_id"] = section_id
        fallback["section_name"] = route_label
        fallback["detail"] = f"Pilih manual · {route_label}"
        return fallback

    return {
        "source": "manual",
        "section_id": section_id,
        "section_name": route_label,
        "entry_gate_code": None,
        "entry_gate_name": section.get("origin_name"),
        "exit_gate_code": None,
        "exit_gate_name": section.get("destination_name"),
        "detail": "Pilih manual · tarif belum tersedia",
        "weight_pct": None,
        "one_way_idr": 0.0,
        "round_trip_idr": 0.0,
        "rates_by_golongan": _section_rates_by_code(section, golongan_code),
    }


def build_manual_toll_breakdown(
    section_ids: list[int],
    sections: list[dict],
    gates: list[dict],
    fares: list[dict],
    golongan_code: str = "II",
) -> dict:
    by_id = {int(s["id"]): s for s in sections if s.get("id") is not None}
    segments: list[dict] = []
    for sid in section_ids:
        section = by_id.get(int(sid))
        if not section:
            continue
        segment = build_segment_for_master_section(section, gates, fares, golongan_code)
        if segment:
            segments.append(segment)

    one_way = sum(float(s.get("one_way_idr") or 0) for s in segments)
    return {
        "segments": segments,
        "one_way_idr": one_way,
        "toll_idr": one_way * 2,
        "toll_source": "manual",
        "toll_is_estimate": False,
        "toll_note": (
            "Tarif ruas tol dipilih manual dari master BPJT. "
            "Total pulang-pergi dikali 2."
        ),
    }


def gate_coordinate_lookup(name: str) -> tuple[float, float] | None:
    return _load_gate_coordinates().get(_normalize_gate_name(name))


def _find_gate_for_segment_side(
    gates: list[dict],
    code: str | None,
    name: str | None,
) -> dict | None:
    if code:
        code_norm = code.strip().upper()
        for gate in gates:
            if (gate.get("code") or "").strip().upper() == code_norm:
                return gate
    if not name:
        return None
    name_norm = _normalize_gate_name(name)
    for gate in gates:
        gate_norm = _normalize_gate_name(gate.get("name") or "")
        if gate_norm == name_norm:
            return gate
    for gate in gates:
        gate_norm = _normalize_gate_name(gate.get("name") or "")
        if name_norm in gate_norm or gate_norm in name_norm:
            return gate
    coords = gate_coordinate_lookup(name)
    if coords:
        return {"name": name, "latitude": coords[0], "longitude": coords[1]}
    return None


def _append_waypoint(
    points: list[tuple[float, float]],
    lat: float,
    lng: float,
) -> None:
    if points:
        prev_lat, prev_lng = points[-1]
        if abs(prev_lat - lat) < 1e-5 and abs(prev_lng - lng) < 1e-5:
            return
    points.append((lat, lng))


def _trip_progress_fraction(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    lat: float,
    lng: float,
) -> float:
    """Posisi relatif sepanjang garis asal→tujuan. >1 berarti melewati tujuan."""
    od_lat = dest_lat - origin_lat
    od_lng = dest_lng - origin_lng
    op_lat = lat - origin_lat
    op_lng = lng - origin_lng
    denom = od_lat * od_lat + od_lng * od_lng
    if denom <= 1e-12:
        return 0.0
    return (op_lat * od_lat + op_lng * od_lng) / denom


def trim_waypoints_before_destination(
    waypoints: list[tuple[float, float]],
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    *,
    max_fraction: float = 1.03,
) -> list[tuple[float, float]]:
    """Buang titik lintasan (dan semua titik setelahnya) yang melewati koordinat tujuan."""
    if not waypoints:
        return waypoints
    trimmed: list[tuple[float, float]] = []
    for wp_lat, wp_lng in waypoints:
        frac = _trip_progress_fraction(origin_lat, origin_lng, dest_lat, dest_lng, wp_lat, wp_lng)
        if frac <= max_fraction:
            trimmed.append((wp_lat, wp_lng))
        else:
            break
    return trimmed


def _segment_routing_text(
    segment: dict,
    sections_by_id: dict[int, dict] | None = None,
) -> str:
    parts = [
        segment.get("section_name") or "",
        segment.get("entry_gate_name") or "",
        segment.get("exit_gate_name") or "",
    ]
    section_id = segment.get("section_id")
    if sections_by_id and section_id is not None:
        master = sections_by_id.get(int(section_id)) or {}
        parts.append(master.get("name") or "")
        parts.append(master.get("origin_name") or "")
        parts.append(master.get("destination_name") or "")
    return _normalize_toll_text(" ".join(parts))


def _coords_for_anchor_name(
    anchor: str,
    gates: list[dict],
) -> tuple[float, float] | None:
    gate = _find_gate_for_segment_side(gates, None, anchor)
    if gate:
        return _gate_coordinates(gate)
    return gate_coordinate_lookup(anchor)


def _corridor_type_key(
    segment: dict,
    sections_by_id: dict[int, dict] | None,
    dest_lat: float,
    dest_lng: float,
) -> str | None:
    text = _segment_routing_text(segment, sections_by_id)
    if any(k in text for k in ("priok", "pelabuhan", "aksestanjung", "tanjungpriok")):
        return "priok"
    if any(k in text for k in ("ctc", "tomang", "cawangtomangpluit")) or (
        "cawang" in text and "pluit" in text
    ):
        return "ctc"
    if any(
        k in text
        for k in (
            "jorr",
            "cilincing",
            "cibungtcilincing",
            "pulogebang",
            "cakung",
            "rorotan",
            "kayubesar",
            "jatiasih",
        )
    ):
        from app.route_profiles import destination_corridor

        return "jorr_east" if destination_corridor(dest_lat, dest_lng) == "east" else "jorr_west"
    if "jakartacikampek" in text:
        return "japek"
    if any(k in text for k in ("cipularang", "purwakarta")) or (
        "cikampek" in text and "padalarang" in text
    ):
        return "cipularang"
    if any(k in text for k in ("padaleunyi", "purbaleunyi")) or (
        "padalarang" in text and "cileunyi" in text
    ):
        return "padaleunyi"
    if "cisumdawu" in text:
        return "cisumdawu"
    if any(k in text for k in ("soedijatmo", "sedyatmo")):
        return "soedijatmo"
    return None


# Urutan gerbang JORR (Penjaringan → selatan → timur → utara → Priok)
_JORR_RING_GATES: list[str] = [
    "Penjaringan",
    "Kayu Besar",
    "Kembangan",
    "Kebon Jeruk",
    "Ulujami",
    "Pondok Pinang",
    "Taman Mini",
    "Cikunir",
    "Jati Asih",
    "Kalimalang",
    "Cakung",
    "Bintara",
    "Cilincing",
    "Rorotan",
    "Kebon Bawang",
]

# Titik jarang untuk OSRM — ikuti JORR luar, bukan Harbor/lingkar dalam.
# Wajib ada titik selatan (Ulujami/Pondok Pinang/Kalimalang): tanpa itu OSRM
# Kayu Besar→Cakung/Bintara sering lewat tol dalam utara (~35 km, bukan JORR).
# Jangan wajibkan Cikunir/Jati Asih: OSRM turun ke Bintaro lalu naik (kotak).
_JORR_ROUTE_SPARSE_GATES: list[str] = [
    "Penjaringan",
    "Kayu Besar",
    "Ulujami",
    "Pondok Pinang",
    "Kalimalang",
    "Cilincing",
    "Rorotan",
    "Kebon Bawang",
]


def _normalize_jorr_gate_label(name: str) -> str:
    n = _normalize_gate_name(name)
    aliases = {
        "kayubesar": "Kayu Besar",
        "jatiasih": "Jati Asih",
        "kebonjeruk": "Kebon Jeruk",
        "pondokpinang": "Pondok Pinang",
        "tamanmini": "Taman Mini",
        "kalimalang": "Kalimalang",
        "cakung": "Cakung",
        "pulogebang": "Cakung",
        "bintara": "Bintara",
        "gtbintarajayadanjakasampurna": "Bintara",
        "gtmargajaya1dan2": "Bintara",
        "kebonbawang": "Kebon Bawang",
        "aksestanjungpriuk": "Kebon Bawang",
        "tanjungpriok": "Kebon Bawang",
        "tanjungpriuk": "Kebon Bawang",
    }
    if n in aliases:
        return aliases[n]
    for gate in _JORR_RING_GATES:
        if _normalize_gate_name(gate) == n:
            return gate
    return (name or "").strip()


def _jorr_ring_index(name: str) -> int | None:
    label = _normalize_jorr_gate_label(name)
    for i, gate in enumerate(_JORR_RING_GATES):
        if _normalize_gate_name(gate) == _normalize_gate_name(label):
            return i
    return None


def _jorr_waypoints_between(entry: str, exit_: str) -> list[str] | None:
    """Titik lintasan sepanjang ring JORR antara gerbang masuk dan keluar."""
    i = _jorr_ring_index(entry)
    j = _jorr_ring_index(exit_)
    if i is None or j is None or i == j:
        return None
    if i < j:
        return _JORR_RING_GATES[i : j + 1]
    # Arah berlawanan: ambil jalur pendek lewat ujung ring (via Priok) atau balik
    forward = _JORR_RING_GATES[i:] + _JORR_RING_GATES[: j + 1]
    backward = list(reversed(_JORR_RING_GATES[j : i + 1]))
    return forward if len(forward) <= len(backward) else backward


def _jorr_sparse_route_waypoints(
    entry: str,
    exit_: str,
    *,
    for_jagorawi_transfer: bool = False,
) -> list[str] | None:
    """
    Waypoint OSRM/peta untuk JORR — subset ring agar tetap di lingkar luar.
    for_jagorawi_transfer=True: potong di Taman Mini (pindah ke Jagorawi).
    """
    full = _jorr_waypoints_between(entry, exit_)
    if not full:
        return None
    if for_jagorawi_transfer:
        full = _clip_jorr_names_at_transfer(full)
        allowed = {
            _normalize_gate_name(g)
            for g in (*_JORR_ROUTE_SPARSE_GATES, _JORR_JAGORAWI_TRANSFER)
        }
    else:
        allowed = {_normalize_gate_name(g) for g in _JORR_ROUTE_SPARSE_GATES}

    sparse: list[str] = []
    for idx, name in enumerate(full):
        keep = idx == 0 or idx == len(full) - 1 or _normalize_gate_name(name) in allowed
        if not keep:
            continue
        if sparse and _normalize_gate_name(sparse[-1]) == _normalize_gate_name(name):
            continue
        sparse.append(name)
    return sparse or full


# SS Taman Mini = perpindahan alami JORR ↔ Jagorawi (ke Bogor/Ciawi).
_JORR_JAGORAWI_TRANSFER = "Taman Mini"


def _is_jorr_ring_pair(entry: str | None, exit_: str | None) -> bool:
    if not entry or not exit_:
        return False
    return _jorr_ring_index(entry) is not None and _jorr_ring_index(exit_) is not None


def _is_jagorawi_bogor_segment(
    segment: dict,
    sections_by_id: dict[int, dict] | None,
) -> bool:
    text = _segment_routing_text(segment, sections_by_id)
    return any(
        k in text
        for k in ("jagorawi", "jakartabogor", "bogorciawi", "ciawi", "cibubur")
    ) and "bocimi" not in text


def _segment_has_jorr_ring(segment: dict) -> bool:
    entry = (segment.get("entry_gate_name") or segment.get("entry_gate_code") or "").strip()
    exit_ = (segment.get("exit_gate_name") or segment.get("exit_gate_code") or "").strip()
    if _is_jorr_ring_pair(entry, exit_):
        return True
    text = _normalize_gate_name(
        f"{segment.get('section_name') or ''} {entry} {exit_}"
    )
    # Jangan anggap ruas Japek "Cikunir → …" sebagai JORR.
    if any(k in text for k in ("jakartacikampek", "cikampek", "japek")):
        return False
    return any(k in text for k in ("jorr", "kayubesar", "jatiasih"))


def _is_japek_segment(
    segment: dict,
    sections_by_id: dict[int, dict] | None,
) -> bool:
    text = _segment_routing_text(segment, sections_by_id)
    if any(k in text for k in ("cipularang", "padalarang", "padaleunyi", "cisumdawu")):
        return False
    return any(
        k in text
        for k in (
            "jakartacikampek",
            "japek",
            "cikampek",
            "cikarang",
            "karawang",
            "cibitung",
            "tambun",
            "bekasibarat",
            "bekasitimur",
            "dawuan",
            "kalihurip",
            "cibatu",
            "jakartaic",
        )
    )


def _clip_jorr_names_at_transfer(
    names: list[str],
    transfer: str = _JORR_JAGORAWI_TRANSFER,
) -> list[str]:
    """Potong lintasan JORR di gerbang pindah ke Jagorawi (hindari mutar ke Cikunir dulu)."""
    if not names:
        return names
    transfer_norm = _normalize_gate_name(transfer)
    clipped: list[str] = []
    for name in names:
        clipped.append(name)
        if _normalize_gate_name(name) == transfer_norm:
            return clipped
    # Transfer tidak ada di list (exit sebelum TMII) — biarkan apa adanya
    exit_idx = _jorr_ring_index(names[-1])
    transfer_idx = _jorr_ring_index(transfer)
    entry_idx = _jorr_ring_index(names[0])
    if (
        entry_idx is not None
        and exit_idx is not None
        and transfer_idx is not None
        and entry_idx < transfer_idx < exit_idx
    ):
        ring = _jorr_waypoints_between(names[0], transfer)
        if ring:
            return ring
    return names


def _corridor_waypoint_names(
    segment: dict,
    sections_by_id: dict[int, dict] | None,
    dest_lat: float,
    dest_lng: float,
) -> list[str] | None:
    """
    Override urutan titik lintasan per koridor.
    Gerbang tarif BPJT (mis. Cawang→Pluit) sering tidak cukup untuk memaksa
    jalur peta lewat koridor sebenarnya (mis. Tanjung Priok di utara).
    """
    text = _segment_routing_text(segment, sections_by_id)
    entry = (segment.get("entry_gate_name") or segment.get("entry_gate_code") or "").strip()
    exit_ = (segment.get("exit_gate_name") or segment.get("exit_gate_code") or "").strip()

    if any(k in text for k in ("priok", "pelabuhan", "aksestanjung", "tanjungpriok")):
        return ["aksestanjungpriuk", "cawang"]
    if any(k in text for k in ("ctc", "tomang", "cawangtomangpluit")) or (
        "cawang" in text and "pluit" in text
    ):
        if entry and exit_:
            return [entry, exit_]
        return ["cawang", "pluit"]
    if any(
        k in text
        for k in (
            "jorr",
            "cilincing",
            "cibungtcilincing",
            "pulogebang",
            "cakung",
            "rorotan",
            "kayubesar",
            "jatiasih",
        )
    ) or (
        entry
        and exit_
        and _jorr_ring_index(entry) is not None
        and _jorr_ring_index(exit_) is not None
    ):
        # Pakai pasangan gerbang yang dipilih manual (Kayu Besar → Jati Asih),
        # jangan diganti waypoint generik Rorotan/Cilincing.
        # Sparse: hindari ramp Pondok Pinang/TMII yang menarik OSRM keluar ring.
        if entry and exit_:
            ring = _jorr_sparse_route_waypoints(entry, exit_)
            if ring:
                return ring
            return [entry, exit_]
        from app.route_profiles import destination_corridor

        if destination_corridor(dest_lat, dest_lng) == "east":
            return ["rorotan", "pulogebang", "cilincing"]
        return ["penjaringan", "ulujami", "rorotan"]
    if any(k in text for k in ("cipularang", "purwakarta")) or (
        "cikampek" in text and "padalarang" in text
    ):
        return ["cikampek", "dawuan", "padalarang"]
    if any(k in text for k in ("padaleunyi", "purbaleunyi")) or (
        "padalarang" in text and "cileunyi" in text
    ):
        return ["padalarang", "pasteur", "cileunyi"]
    if "cisumdawu" in text:
        return ["cileunyi", "paseh", "cisumdawuutama"]
    if any(k in text for k in ("jagorawi", "jakartabogor", "bogorciawi")) or (
        "ciawi" in text and "jakarta" in text
    ):
        # Ke Bogor/Ciawi: jangan tarik balik ke Cawang jika sudah lewat Taman Mini.
        if exit_ and "ciawi" in _normalize_gate_name(exit_):
            return [_JORR_JAGORAWI_TRANSFER, "cibubur", exit_]
        if entry and exit_:
            return [entry, exit_]
        return [_JORR_JAGORAWI_TRANSFER, "cibubur", "ciawi"]
    if any(k in text for k in ("jakartacikampek", "japek")) or (
        entry and "cikunir" in _normalize_gate_name(entry) and exit_
    ):
        entry_norm = _normalize_gate_name(entry)
        if entry_norm in ("jakartaic", "jakarta", "halim"):
            return ["Cikunir", exit_] if exit_ else ["Cikunir"]
        if entry and exit_:
            return [entry, exit_]
    return None


def _gate_names_in_travel_order(
    segment: dict,
    gates: list[dict],
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    sections_by_id: dict[int, dict] | None,
) -> list[str]:
    """Urutkan gerbang sepanjang arah perjalanan asal→tujuan."""
    progress = lambda lat, lng: _trip_progress_fraction(
        origin_lat, origin_lng, dest_lat, dest_lng, lat, lng
    )
    fixed = _corridor_waypoint_names(segment, sections_by_id, dest_lat, dest_lng)
    if fixed:
        # Pertahankan urutan koridor (mis. ring JORR Kayu Besar→Jati Asih).
        # Jangan di-sort ulang menurut garis lurus gudang→customer.
        ordered: list[str] = []
        seen: set[str] = set()
        for name in fixed:
            coords = _coords_for_anchor_name(name, gates)
            if not coords:
                continue
            norm = _normalize_gate_name(name)
            if norm in seen:
                continue
            seen.add(norm)
            ordered.append(name)
        if ordered:
            return ordered

    candidates = []
    seen_c: set[str] = set()
    for code_key, name_key in (
        ("entry_gate_code", "entry_gate_name"),
        ("exit_gate_code", "exit_gate_name"),
    ):
        for val in (segment.get(name_key), segment.get(code_key)):
            if not val:
                continue
            label = str(val).strip()
            norm = _normalize_gate_name(label)
            if not norm or norm in seen_c:
                continue
            seen_c.add(norm)
            candidates.append(label)

    scored: list[tuple[float, str]] = []
    for name in candidates:
        coords = _coords_for_anchor_name(name, gates)
        if coords:
            scored.append((progress(coords[0], coords[1]), name))
    scored.sort(key=lambda row: row[0])
    return [name for _, name in scored]


def segments_need_jorr_jagorawi_transfer(segments: list[dict]) -> bool:
    """True jika kombinasi JORR + Jagorawi/Bogor — lintasan dipotong di Taman Mini."""
    return any(_segment_has_jorr_ring(s) for s in segments) and any(
        _is_jagorawi_bogor_segment(s, None) for s in segments
    )


def segments_need_jorr_japek_transfer(segments: list[dict]) -> bool:
    """True jika kombinasi JORR + Japek — lanjut dari Cikunir, jangan balik Halim/Jakarta IC."""
    return any(_segment_has_jorr_ring(s) for s in segments) and any(
        _is_japek_segment(s, None) for s in segments
    )


def toll_segment_map_geometry(
    segment: dict,
    gates: list[dict],
    *,
    clip_jorr_at_transfer: bool = False,
) -> list[list[float]]:
    """Garis ruas tol di peta: ikuti gerbang sepanjang koridor bila ada."""
    entry = (segment.get("entry_gate_name") or segment.get("entry_gate_code") or "").strip()
    exit_ = (segment.get("exit_gate_name") or segment.get("exit_gate_code") or "").strip()
    names: list[str] = []
    if entry and exit_ and _jorr_ring_index(entry) is not None and _jorr_ring_index(exit_) is not None:
        names = (
            _jorr_sparse_route_waypoints(
                entry,
                exit_,
                for_jagorawi_transfer=clip_jorr_at_transfer,
            )
            or [entry, exit_]
        )
    elif clip_jorr_at_transfer and _is_jagorawi_bogor_segment(segment, None):
        # Overlay Jagorawi: jangan ulang Taman Mini (sudah ujung overlay JORR)
        exit_name = exit_ or "Ciawi"
        names = ["Cibubur", exit_name]
    elif _is_japek_segment(segment, None):
        # Japek (terutama setelah JORR): mulai Cikunir, jangan Jakarta IC/Halim
        entry_norm = _normalize_gate_name(entry)
        exit_name = exit_ or "Cikampek"
        if entry_norm in ("jakartaic", "jakarta", "halim") or not entry:
            names = ["Cikunir", exit_name]
        else:
            names = [entry, exit_name]
    else:
        for code_key, name_key in (
            ("entry_gate_code", "entry_gate_name"),
            ("exit_gate_code", "exit_gate_name"),
        ):
            for val in (segment.get(name_key), segment.get(code_key)):
                if val:
                    names.append(str(val).strip())
                    break

    geometry: list[list[float]] = []
    for name in names:
        coords = _coords_for_anchor_name(name, gates)
        if not coords:
            continue
        lat, lng = coords
        if geometry and abs(geometry[-1][0] - lat) < 1e-5 and abs(geometry[-1][1] - lng) < 1e-5:
            continue
        geometry.append([lat, lng])
    return geometry


def filter_monotonic_waypoints(
    waypoints: list[tuple[float, float]],
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> list[tuple[float, float]]:
    """Buang titik yang mundur atau terlalu jauh dari arah asal→tujuan."""
    if not waypoints:
        return waypoints
    sorted_wps = sorted(
        waypoints,
        key=lambda c: _trip_progress_fraction(origin_lat, origin_lng, dest_lat, dest_lng, c[0], c[1]),
    )
    filtered: list[tuple[float, float]] = []
    last_frac = -0.05
    for lat, lng in sorted_wps:
        frac = _trip_progress_fraction(origin_lat, origin_lng, dest_lat, dest_lng, lat, lng)
        if frac < -0.02 or frac > 1.05:
            continue
        if frac <= last_frac + 0.015:
            continue
        filtered.append((lat, lng))
        last_frac = frac
    return filtered


def waypoints_from_toll_segments(
    segments: list[dict],
    gates: list[dict],
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    sections: list[dict] | None = None,
) -> list[tuple[float, float]]:
    """Titik lintasan OSRM — per ruas tol, urut sepanjang asal→tujuan."""
    sections_by_id = {
        int(s["id"]): s for s in (sections or []) if s.get("id") is not None
    }
    progress = lambda lat, lng: _trip_progress_fraction(
        origin_lat, origin_lng, dest_lat, dest_lng, lat, lng
    )
    corridor_seen: set[str] = set()
    groups: list[tuple[int, list[tuple[float, float]]]] = []
    preserve_corridor_order = False

    has_jorr_ring = any(_segment_has_jorr_ring(seg) for seg in segments)
    has_jagorawi = any(
        _is_jagorawi_bogor_segment(seg, sections_by_id) for seg in segments
    )
    has_japek = any(_is_japek_segment(seg, sections_by_id) for seg in segments)
    # Kayu Besar→Cikunir + Jakarta→Ciawi: jangan mutar JORR sampai Cikunir dulu.
    clip_jorr_for_jagorawi = has_jorr_ring and has_jagorawi
    # Kayu Besar→Cikunir + Japek: lanjut dari Cikunir, jangan balik Halim.
    join_jorr_japek = has_jorr_ring and has_japek

    for segment in segments:
        ctype = _corridor_type_key(segment, sections_by_id, dest_lat, dest_lng)
        if ctype and ctype in corridor_seen:
            continue
        if ctype:
            corridor_seen.add(ctype)

        entry = (segment.get("entry_gate_name") or segment.get("entry_gate_code") or "").strip()
        exit_ = (segment.get("exit_gate_name") or segment.get("exit_gate_code") or "").strip()
        is_jorr_pair = _is_jorr_ring_pair(entry, exit_)
        is_jagorawi = _is_jagorawi_bogor_segment(segment, sections_by_id)
        is_japek = _is_japek_segment(segment, sections_by_id)
        if is_jorr_pair:
            preserve_corridor_order = True
        if clip_jorr_for_jagorawi and (is_jorr_pair or is_jagorawi):
            preserve_corridor_order = True
        if join_jorr_japek and (is_jorr_pair or is_japek):
            preserve_corridor_order = True

        names = _gate_names_in_travel_order(
            segment,
            gates,
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            sections_by_id,
        )
        if is_jorr_pair:
            sparse = _jorr_sparse_route_waypoints(
                entry,
                exit_,
                for_jagorawi_transfer=clip_jorr_for_jagorawi,
            )
            if sparse:
                names = sparse
        if clip_jorr_for_jagorawi and is_jagorawi:
            # Lanjut Jagorawi tanpa mengulang Taman Mini (hindari knot di SS).
            exit_name = exit_ or "Ciawi"
            names = ["Cibubur", exit_name]
        if join_jorr_japek and is_japek:
            exit_name = exit_ or "Cikampek"
            entry_norm = _normalize_gate_name(entry)
            if entry_norm in ("jakartaic", "jakarta", "halim") or not entry:
                names = ["Cikunir", exit_name]
            else:
                names = [entry, exit_name]

        group: list[tuple[float, float]] = []
        for name in names:
            coords = _coords_for_anchor_name(name, gates)
            if coords:
                group.append(coords)
        if group:
            # Urutan: JORR (0), Japek (1), Jagorawi (2), lain (3)
            if is_jorr_pair or (_segment_has_jorr_ring(segment) and not is_jagorawi and not is_japek):
                order_key = 0
            elif is_japek:
                order_key = 1
            elif is_jagorawi:
                order_key = 2
            else:
                order_key = 3
            groups.append((order_key, group))

    if clip_jorr_for_jagorawi or join_jorr_japek:
        groups.sort(key=lambda row: row[0])
    elif not preserve_corridor_order:
        groups.sort(key=lambda row: progress(row[1][0][0], row[1][0][1]))

    points: list[tuple[float, float]] = []
    for _, group in groups:
        for lat, lng in group:
            _append_waypoint(points, lat, lng)

    if preserve_corridor_order:
        # Jangan sort/filter menurut garis lurus gudang→customer (merusak ring JORR).
        return points

    points = filter_monotonic_waypoints(
        trim_waypoints_before_destination(
            points,
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
        ),
        origin_lat,
        origin_lng,
        dest_lat,
        dest_lng,
    )
    return points


def refresh_gate_coordinates(db) -> dict:
    """Apply bundled toll_gate_coordinates.json to all gates in DB."""
    from app.models import TollGate

    coords = _load_gate_coordinates()
    updated = 0
    skipped: list[str] = []
    for gate in db.scalars(select(TollGate)).all():
        key = _normalize_gate_name(gate.name or "")
        point = coords.get(key)
        if not point:
            skipped.append(gate.name or f"id={gate.id}")
            continue
        gate.latitude = round(point[0], 6)
        gate.longitude = round(point[1], 6)
        updated += 1
    db.commit()
    return {"updated": updated, "skipped": skipped, "total": updated + len(skipped)}


def serialize_gate_fare_context(gates_rows, fare_rows) -> dict:
    gates = []
    for g in gates_rows:
        lat = float(g.latitude) if g.latitude is not None else None
        lng = float(g.longitude) if g.longitude is not None else None
        if lat is None or lng is None:
            builtin = gate_coordinate_lookup(g.name or "")
            if builtin:
                lat, lng = builtin
        gates.append(
            {
                "id": g.id,
                "section_id": g.section_id,
                "section_name": g.section.name if g.section else None,
                "section_length_km": float(g.section.length_km) if g.section else None,
                "code": g.code,
                "name": g.name,
                "latitude": lat,
                "longitude": lng,
                "sort_order": g.sort_order,
                "is_active": g.is_active,
            }
        )
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
