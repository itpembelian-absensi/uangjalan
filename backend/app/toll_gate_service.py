from __future__ import annotations

import math
import re

TOLL_NOTE_BPJT = (
    "Tarif berdasarkan ruas tol yang dilalui di peta (rute OSRM), dicocokkan ke master gerbang BPJT. "
    "Total pulang-pergi dikali 2."
)

# Koordinat acuan gerbang — dipakai jika belum diisi di database.
BUILTIN_GATE_COORDINATES: dict[str, tuple[float, float]] = {
    # Japek
    "jakartaic": (-6.2165, 106.9368),
    "pondokgedebarattimur": (-6.2815, 106.9175),
    "cikunir": (-6.2678, 106.9785),
    "bekasibarat": (-6.2385, 106.9895),
    "bekasitimur": (-6.2495, 107.0228),
    "tambun": (-6.2125, 107.0575),
    "cibitung": (-6.2195, 107.1035),
    "cikarangbarat": (-6.2615, 107.1385),
    "cibatu": (-6.2885, 107.1225),
    "cikarangtimur": (-6.2925, 107.1685),
    "karawangbarat": (-6.3115, 107.2685),
    "karawangtimur": (-6.3250, 107.3350),
    "dawuan": (-6.3480, 107.4120),
    "kalihurip": (-6.3610, 107.4680),
    "cikampek": (-6.4190, 107.4640),
    # Jabodetabek utara / dalam kota
    "profdrirsoedijatmo": (-6.1260, 106.6550),
    "cawang": (-6.2440, 106.8720),
    "tomang": (-6.1780, 106.7980),
    "pluit": (-6.1120, 106.7930),
    "jembatantigapluit": (-6.1080, 106.7880),
    "aksestanjungpriuk": (-6.1040, 106.8810),
    "seksie1e2e2a": (-6.0980, 106.9050),
    "penjaringan": (-6.1180, 106.8050),
    "kebonjeruk": (-6.1920, 106.7680),
    "ulujami": (-6.2880, 106.7380),
    "pondokpinang": (-6.2650, 106.7780),
    "tamanmini": (-6.3030, 106.8910),
    "rorotan": (-6.1450, 106.9280),
    "kebonbawang": (-6.1550, 106.7980),
    "jakarta": (-6.2940, 106.8710),
    "ciawi": (-6.7370, 106.8480),
    "jcbenda": (-6.1220, 106.6920),
    "bendautama": (-6.1280, 106.7020),
    "batuceper": (-6.1550, 106.6780),
    "cengkareng": (-6.1380, 106.7180),
    "tanatinggi": (-6.1750, 106.6520),
    "pinang": (-6.1980, 106.6280),
    "jckunciran": (-6.2080, 106.5980),
    "jcserpong": (-6.2850, 106.6680),
    "ssparigi": (-6.3120, 106.6480),
    "jakartadalamkota": (-6.244, 106.873),
    "jakartaic": (-6.244, 106.873),
    "cibubur": (-6.376, 106.902),
    "gunungputri": (-6.438, 106.892),
    "citeureup": (-6.488, 106.883),
    "cibinong": (-6.498, 106.873),
    "sentulselatan": (-6.568, 106.863),
    "sentulbarat": (-6.562, 106.852),
    "bogor": (-6.600, 106.820),
}

# (kata kunci di nama ruas tol OSRM, kata kunci di nama ruas/gerbang BPJT)
SECTION_ROUTE_HINTS: list[tuple[list[str], list[str]]] = [
    (["sedyatmo", "soedijatmo"], ["sedyatmo", "soedijatmo"]),
    (["pelabuhan", "priok", "tanjungpriuk"], ["priok", "pelabuhan", "tanjungpriuk", "aksestanjung"]),
    (["ancol", "jembatantiga", "pluit"], ["ancol", "pluit", "jembatantiga", "priok", "cawang"]),
    (["cawang", "tomang", "dalamkota", "cawangpluit"], ["cawang", "ctc", "tomang", "dalamkota", "pluit"]),
    (["cikampek", "japek"], ["cikampek", "japek"]),
    (["bekasi", "cikarang", "karawang", "tambun", "cibitung"], ["cikampek", "japek", "bekasi", "cikarang", "karawang", "tambun"]),
    (["jorr", "lingkarluar", "outer"], ["jorr", "lingkarluar"]),
    (["bogor", "ciawi", "jagorawi", "cinere"], ["bogor", "ciawi", "jagorawi", "cinere"]),
    (["kelapagading", "pulogebang"], ["dalamkota", "kelapagading", "pulogebang"]),
    (["cengkareng", "batuceper"], ["cengkareng", "batuceper", "benda"]),
    (["kunciran", "serpong"], ["kunciran", "serpong"]),
    (["jakartabogor", "jagorawi"], ["bogor", "ciawi", "jagorawi", "jakartabogor"]),
    (["lingkardalam", "inner"], ["dalamkota", "ctc", "lingkardalam"]),
    (["tomang", "cawangpluit"], ["cawang", "ctc", "tomang", "pluit", "dalamkota"]),
    (["cinere"], ["cinere", "jagorawi", "cimanggis"]),
    (["bekasicawang", "bckm"], ["bekasi", "cawang", "kampungmelayu"]),
    (["cimanggis", "cibitung"], ["cimanggis", "cibitung", "jatikarya"]),
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
    return BUILTIN_GATE_COORDINATES.get(key)


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
    return BUILTIN_GATE_COORDINATES.get(_normalize_gate_name(name))


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
