from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

from fastapi import HTTPException

from app.core.config import settings
from app.toll_gate_service import (
    TOLL_NOTE_BPJT,
    _road_looks_like_ferry,
    breakdown_from_route_sections_only,
    estimate_toll_bpjt_breakdown,
    estimate_toll_bpjt_gates,
    haversine_km,
)

USER_AGENT = "UangPengiriman/1.0 (https://github.com/uangpengiriman)"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODE_BASE = "https://maps.googleapis.com/maps/api/geocode/json"


def osrm_base_url() -> str:
    base = (settings.osrm_base_url or "").strip().rstrip("/")
    return base or "https://router.project-osrm.org/route/v1/driving"

TOLL_VEHICLE_ORDER = ("grandmax", "engkle", "double", "fuso", "tronton")

VEHICLE_TOLL_CLASS: dict[str, dict[str, str]] = {
    "grandmax": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "engkle": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "double": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "fuso": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "tronton": {"golongan_code": "III", "golongan": "III", "gandar": "3 gandar"},
}

TOLL_NOTE_JABODETABEK = (
    "Estimasi ruas tol (fallback jika tarif gerbang BPJT/Jasa Marga belum diisi). "
    "Isi master Gerbang Tol + tarif antar gerbang dari daftar resmi BPJT/Jasa Marga."
)


def _default_sections_from_settings() -> list[dict]:
    return [
        {
            "key": "japek",
            "name": "Japek (Jakarta–Cikampek)",
            "length_km": settings.toll_japek_km,
            "gol23": settings.toll_japek_gol23,
            "gol45": settings.toll_japek_gol45,
        },
        {
            "key": "jorr",
            "name": "JORR",
            "length_km": settings.toll_jorr_km,
            "gol23": settings.toll_jorr_gol23,
            "gol45": settings.toll_jorr_gol45,
        },
        {
            "key": "jakarta_inner",
            "name": "Dalam Kota & Sedyatmo",
            "length_km": settings.toll_jakarta_inner_km,
            "gol23": settings.toll_jakarta_inner_gol23,
            "gol45": settings.toll_jakarta_inner_gol45,
        },
        {
            "key": "jagorawi",
            "name": "Jagorawi",
            "length_km": settings.toll_jagorawi_km,
            "gol23": settings.toll_jagorawi_gol23,
            "gol45": settings.toll_jagorawi_gol45,
        },
    ]


def serialize_toll_sections(rows) -> list[dict]:
    result = []
    for row in rows:
        rates_by_code: dict[str, float] = {}
        rates_list = []
        for rate_row in getattr(row, "rates", []) or []:
            gol = rate_row.golongan
            if gol is None:
                continue
            code = gol.code
            amount = float(rate_row.rate)
            rates_by_code[code] = amount
            rates_list.append(
                {
                    "golongan_id": gol.id,
                    "golongan_name": gol.name,
                    "golongan_code": code,
                    "rate": amount,
                }
            )

        gol23 = rates_by_code.get("II", rates_by_code.get("III", float(row.gol23)))
        gol45 = rates_by_code.get("IV", rates_by_code.get("V", float(row.gol45)))

        result.append(
            {
                "key": f"section_{row.id}",
                "id": row.id,
                "name": row.name,
                "origin_name": row.origin_name,
                "destination_name": row.destination_name,
                "length_km": float(row.length_km),
                "gol23": gol23,
                "gol45": gol45,
                "rates_by_code": rates_by_code,
                "rates": rates_list,
                "sort_order": row.sort_order,
                "is_active": row.is_active,
            }
        )
    return result


def _normalize_section_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def collapse_sections_for_routing(sections: list[dict]) -> list[dict]:
    """
    Gabungkan baris ruas duplikat (nama sama, gerbang keluar berbeda) menjadi satu
    baris acuan ruas penuh — dipakai untuk perhitungan rute, bukan tampilan master.
    """
    grouped: dict[str, list[dict]] = {}
    for sec in sections:
        key = _normalize_section_name(sec.get("name") or "")
        grouped.setdefault(key, []).append(sec)

    collapsed: list[dict] = []
    for group in grouped.values():
        if len(group) == 1:
            collapsed.append(group[0])
            continue
        collapsed.append(max(group, key=lambda s: float(s.get("gol23") or 0)))

    collapsed.sort(key=lambda s: (s.get("sort_order") or 0, s.get("name") or ""))
    return collapsed


def _section_rate_for_golongan(section: dict, golongan_code: str) -> float:
    rates_by_code = section.get("rates_by_code") or {}
    if golongan_code in rates_by_code:
        return rates_by_code[golongan_code]
    if golongan_code in ("II", "III"):
        return section.get("gol23", 0)
    return section.get("gol45", 0)


def get_toll_reference(sections: list[dict] | None = None) -> dict:
    sections = sections or _default_sections_from_settings()
    return {
        "sections": sections,
        "note": TOLL_NOTE_JABODETABEK,
    }


def _section_weights(distance_km: float, sections: list[dict]) -> dict[str, float]:
    if not sections:
        return {}

    keys = [sec["key"] for sec in sections]
    count = len(keys)
    weights = [0.0] * count

    if distance_km <= 15:
        weights[0] = 0.70
        if count > 1:
            weights[1] = 0.30
    elif distance_km <= 35:
        for i in range(count):
            weights[i] = max(0.05, (count - i) / sum(range(1, count + 1)))
    elif distance_km <= 60:
        for i in range(count):
            weights[i] = 1.0 / count * (0.6 + 0.4 * (i + 1) / count)
    else:
        for i in range(count):
            weights[i] = 1.0 / count

    total = sum(weights) or 1.0
    return {keys[i]: weights[i] / total for i in range(count)}


def _gol45_multiplier(sections: list[dict], golongan_code: str) -> float:
    base = _section_rate_for_golongan(sections[0], "II") if sections else 0
    target = _section_rate_for_golongan(sections[0], golongan_code) if sections else 0
    if base > 0:
        return target / base
    return 1.33


def estimate_jabodetabek_toll(
    distance_km: float,
    golongan_code: str = "II",
    sections: list[dict] | None = None,
) -> float:
    if distance_km <= 0:
        return 0.0

    sections = sections or _default_sections_from_settings()
    weights = _section_weights(distance_km, sections)
    total = 0.0

    for sec in sections:
        weight = weights.get(sec["key"], 0.0)
        if weight <= 0:
            continue
        section_rate = _section_rate_for_golongan(sec, golongan_code)
        rate_per_km = section_rate / sec["length_km"]
        total += distance_km * weight * rate_per_km

    return round(total, 0)


def jabodetabek_toll_breakdown(
    distance_km: float,
    golongan_code: str = "II",
    sections: list[dict] | None = None,
) -> dict:
    """Breakdown estimasi ruas tol Jabodetabek per bobot jarak."""
    sections = sections or _default_sections_from_settings()
    if distance_km <= 0 or not sections:
        return {"one_way_idr": 0.0, "segments": []}

    weights = _section_weights(distance_km, sections)
    segments: list[dict] = []
    total = 0.0

    for sec in sections:
        weight = weights.get(sec["key"], 0.0)
        if weight <= 0.001:
            continue
        section_rate = _section_rate_for_golongan(sec, golongan_code)
        rate_per_km = section_rate / sec["length_km"]
        one_way = round(distance_km * weight * rate_per_km, 0)
        total += one_way
        segments.append(
            {
                "source": "section",
                "section_name": sec["name"],
                "entry_gate_code": None,
                "entry_gate_name": sec.get("origin_name"),
                "exit_gate_code": None,
                "exit_gate_name": sec.get("destination_name"),
                "detail": f"Bobot estimasi {round(weight * 100, 1):g}%",
                "weight_pct": round(weight * 100, 1),
                "one_way_idr": one_way,
                "round_trip_idr": one_way * 2,
                "rates_by_golongan": sec.get("rates_by_code") or {},
            }
        )

    return {"one_way_idr": round(total, 0), "segments": segments}


def _normalize_vehicle_key(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "")


def vehicle_toll_allowed(name: str) -> bool:
    """Viar tidak diperbolehkan melalui jalan tol."""
    return "viar" not in _normalize_vehicle_key(name)


def _match_toll_vehicle_key(name: str) -> str | None:
    normalized = _normalize_vehicle_key(name)
    for key in TOLL_VEHICLE_ORDER:
        if key in normalized or normalized in key:
            return key
    return None


def estimate_tolls_by_vehicle(
    distance_km: float,
    vehicle_types: list[tuple[int, str, str | None, str | None]],
    *,
    base_toll_idr: float,
    toll_is_estimate: bool,
    sections: list[dict] | None = None,
) -> list[dict]:
    sections = sections or _default_sections_from_settings()
    results: list[dict] = []

    for type_id, type_name, golongan_code, golongan_name in vehicle_types:
        key = _match_toll_vehicle_key(type_name)
        meta = VEHICLE_TOLL_CLASS.get(key, {}) if key else {}

        resolved_code = golongan_code or meta.get("golongan_code")
        if not vehicle_toll_allowed(type_name):
            results.append(
                {
                    "vehicle_type_id": type_id,
                    "vehicle_type_name": type_name,
                    "golongan": resolved_code or "-",
                    "gandar": "-",
                    "toll_idr": 0.0,
                    "rate_per_km": 0.0,
                }
            )
            continue
        if not resolved_code:
            continue

        gandar = meta.get("gandar", "-")

        if toll_is_estimate and base_toll_idr == 0:
            # Rute tidak melewati jalan tol → tol = 0
            toll = 0.0
        elif toll_is_estimate:
            toll = estimate_jabodetabek_toll(distance_km, resolved_code, sections) * 2
        elif resolved_code == "II":
            toll = round(base_toll_idr, 0)
        else:
            toll = round(base_toll_idr * _gol45_multiplier(sections, resolved_code), 0)

        # Bulatkan ke atas (ribuan)
        if toll > 0:
            toll = float(((int(toll) + 999) // 1000) * 1000)

        rate_per_km = round(toll / distance_km, 0) if distance_km else 0.0
        results.append(
            {
                "vehicle_type_id": type_id,
                "vehicle_type_name": type_name,
                "golongan": resolved_code,
                "gandar": gandar,
                "toll_idr": toll,
                "rate_per_km": rate_per_km,
            }
        )

    return sorted(results, key=lambda item: item["vehicle_type_name"].lower())


def _http_get_json(url: str, headers: dict | None = None, _max_retries: int | None = None) -> object:
    req_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    retries = settings.osrm_max_retries if _max_retries is None else _max_retries
    timeout = settings.osrm_http_timeout
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503) and attempt < retries:
                delay = min(2 ** attempt, 8)  # 1s, 2s, 4s
                time.sleep(delay)
                last_exc = e
                continue
            if e.code == 403:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Layanan peta gagal (403 Forbidden). "
                        "Nominatim memblokir request. "
                        "Solusi: isi GOOGLE_MAPS_API_KEY di file .env, "
                        "atau coba lagi beberapa menit kemudian."
                    ),
                ) from e
            raise HTTPException(status_code=502, detail=f"Layanan peta gagal ({e.code})") from e
        except urllib.error.URLError as e:
            if attempt < retries:
                delay = min(2 ** attempt, 8)
                time.sleep(delay)
                last_exc = e
                continue
            raise HTTPException(status_code=502, detail="Tidak dapat terhubung ke layanan peta/rute") from e
    raise HTTPException(status_code=502, detail=f"Layanan peta gagal setelah {retries} percobaan") from last_exc


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _province_for_city(city: str | None) -> str | None:
    city_n = _normalize_text(city)
    if not city_n or "jakarta" in city_n:
        return None
    jabar_markers = (
        "bekasi",
        "depok",
        "bogor",
        "tangerang",
        "cikarang",
        "karawang",
        "purwakarta",
        "subang",
        "bandung",
        "cirebon",
        "sukabumi",
        "cianjur",
        "garut",
        "tasikmalaya",
        "sumedang",
        "indramayu",
        "majalengka",
        "kuningan",
        "ciamis",
        "pangandaran",
        "banjar",
    )
    if any(marker in city_n for marker in jabar_markers):
        return "Jawa Barat"
    banten_markers = (
        "serang",
        "cilegon",
        "pandeglang",
        "lebak",
        "rangkasbitung",
    )
    if any(marker in city_n for marker in banten_markers):
        return "Banten"
    jateng_markers = (
        "semarang",
        "solo",
        "surakarta",
        "pekalongan",
        "tegal",
        "brebes",
        "cilacap",
        "purwokerto",
        "banyumas",
        "kebumen",
        "magelang",
        "klaten",
        "boyolali",
        "demak",
        "kendal",
        "kudus",
        "jepara",
        "pati",
        "blora",
        "rembang",
        "purbalingga",
        "banjarnegara",
        "wonosobo",
        "temanggung",
        "batang",
        "pemalang",
        "karanganyar",
        "sragen",
        "wonogiri",
        "sukoharjo",
        "grobogan",
    )
    if any(marker in city_n for marker in jateng_markers):
        return "Jawa Tengah"
    jatim_markers = (
        "surabaya",
        "malang",
        "kediri",
        "sidoarjo",
        "gresik",
        "mojokerto",
        "pasuruan",
        "probolinggo",
        "jember",
        "banyuwangi",
        "madiun",
        "ngawi",
        "ponorogo",
        "tulungagung",
        "blitar",
        "lamongan",
        "tuban",
        "bojonegoro",
    )
    if any(marker in city_n for marker in jatim_markers):
        return "Jawa Timur"
    return None


def _geocode_query_variants(
    address: str | None, kelurahan: str | None = None, kecamatan: str | None = None, city: str | None = None, name: str | None = None
) -> list[str]:
    addr = (address or "").strip()
    kel = (kelurahan or "").strip()
    kec = (kecamatan or "").strip()
    city_s = (city or "").strip()
    name_s = (name or "").strip()
    province = _province_for_city(city_s)
    queries: list[str] = []

    def add(*parts: str) -> None:
        cleaned = ", ".join(p.strip() for p in parts if p and p.strip())
        if cleaned and cleaned.lower() not in {q.lower() for q in queries}:
            queries.append(cleaned)

    # --- Kelurahan/Kecamatan-focused queries (highest priority) ---
    # These structured queries help Nominatim find Indonesian villages/subdistricts.
    if kel and kec and city_s:
        if province:
            add(kel, kec, city_s, province, "Indonesia")
            add(f"Kelurahan {kel}", f"Kecamatan {kec}", city_s, province, "Indonesia")
            add(f"Desa {kel}", f"Kecamatan {kec}", city_s, province, "Indonesia")
        add(kel, kec, city_s, "Indonesia")
        add(f"Kelurahan {kel}", f"Kecamatan {kec}", city_s, "Indonesia")
    elif kel and city_s:
        if province:
            add(kel, city_s, province, "Indonesia")
        add(kel, city_s, "Indonesia")
    elif kec and city_s:
        if province:
            add(kec, city_s, province, "Indonesia")
        add(kec, city_s, "Indonesia")

    # --- Full address queries ---
    if addr and city_s:
        if province:
            add(addr, kel, kec, city_s, province, "Indonesia")
        add(addr, kel, kec, city_s, "Indonesia")
        add(addr, city_s, "Indonesia")

    if addr:
        add(addr, "Indonesia")
    if name_s and addr:
        add(name_s, addr, kel, kec, city_s, "Indonesia")
    elif name_s:
        add(name_s, kel, kec, city_s, "Indonesia")

    # --- Kecamatan-only fallback (broader area) ---
    if kec and city_s:
        if province:
            add(f"Kecamatan {kec}", city_s, province, "Indonesia")
        add(f"Kecamatan {kec}", city_s, "Indonesia")

    addr_n = _normalize_text(addr)
    if "terminal" in addr_n and city_s:
        add(f"terminal, {city_s}", province or "", "Indonesia")
        add(f"terminal, {city_s}", "Indonesia")
        rest = re.sub(r"(?i)^terminal\s*", "", addr).strip()
        if rest and _normalize_text(rest) != _normalize_text(city_s):
            add(f"terminal {rest}", city_s, province or "", "Indonesia")

    if "timur" in addr_n and "bekasi" in addr_n:
        add("bekasi timur", city_s or "Bekasi", province or "Jawa Barat", "Indonesia")

    return queries


def _admin_city_matches(display_name: str, city: str | None) -> bool:
    city_n = _normalize_text(city)
    if not city_n:
        return True
    dn = f", {_normalize_text(display_name)},"
    markers = (
        f", {city_n},",
        f", kab {city_n},",
        f", kota {city_n},",
        f", {city_n} ",
    )
    return any(marker in dn for marker in markers)


def _admin_city_conflicts(display_name: str, city: str | None) -> bool:
    city_n = _normalize_text(city)
    if not city_n:
        return False
    dn = _normalize_text(display_name)
    if _admin_city_matches(display_name, city):
        return False
    if "bekasi" in city_n:
        return any(
            marker in dn
            for marker in (
                "jakarta timur",
                "jakarta barat",
                "jakarta selatan",
                "jakarta pusat",
                "jakarta utara",
                "dki jakarta",
            )
        )
    if "jakarta" in city_n:
        return "bekasi" in dn and "jakarta" not in dn
    return False


def _score_geocode_candidate(
    item: dict,
    address: str | None,
    kelurahan: str | None,
    kecamatan: str | None,
    city: str | None,
    name: str | None,
) -> float:
    display_name = item.get("display_name") or ""
    result_name = item.get("name") or ""
    display_n = _normalize_text(display_name)
    result_name_n = _normalize_text(result_name)
    address_n = _normalize_text(address)
    city_n = _normalize_text(city)
    name_n = _normalize_text(name)

    score = float(item.get("importance") or 0) * 100

    if city_n:
        if _admin_city_matches(display_name, city):
            score += 120
        if _admin_city_conflicts(display_name, city):
            score -= 250

    # --- Kelurahan / Kecamatan matching ---
    kel_n = _normalize_text(kelurahan)
    kec_n = _normalize_text(kecamatan)
    address_details = item.get("address") or {}
    nominatim_village = _normalize_text(
        address_details.get("village")
        or address_details.get("suburb")
        or address_details.get("neighbourhood")
    )
    nominatim_district = _normalize_text(
        address_details.get("county")
        or address_details.get("city_district")
        or address_details.get("district")
    )

    if kel_n:
        if kel_n in nominatim_village or kel_n in result_name_n:
            score += 80
        elif kel_n in display_n:
            score += 40
    if kec_n:
        if kec_n in nominatim_district or kec_n in display_n:
            score += 50

    # Prefer village/suburb type results when kelurahan is specified
    if kel_n and item.get("type") in {"village", "suburb", "neighbourhood", "hamlet"}:
        score += 30

    skip_tokens = {
        "terminal",
        "indonesia",
        "jalan",
        "jl",
        "no",
        "rt",
        "rw",
        "kota",
        "kab",
    }
    tokens = [
        token
        for token in re.split(r"[\s,.-]+", address_n)
        if len(token) >= 3 and token not in skip_tokens
    ]
    for token in tokens:
        if token in result_name_n:
            score += 35
        elif token in display_n:
            score += 12
        else:
            score -= 8

    if name_n:
        if name_n in result_name_n or name_n in display_n:
            score += 20

    if item.get("class") == "amenity" and item.get("type") in {"bus_station", "terminal"}:
        score += 25
    if "terminal" in address_n:
        if item.get("class") == "amenity" and item.get("type") == "bus_station":
            score += 45
        if "terminal" in result_name_n:
            score += 40
        if item.get("type") in {"suburb", "village", "town", "city", "administrative"}:
            score -= 45
    elif item.get("type") in {"suburb", "village", "town", "city"}:
        # Don't penalize village/suburb if kelurahan was specified
        if not kel_n:
            score -= 15

    return score


_nominatim_last_call: float = 0.0


def _nominatim_search(query: str, limit: int = 8) -> list[dict]:
    global _nominatim_last_call
    # Nominatim requires max 1 request per second
    elapsed = time.time() - _nominatim_last_call
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _nominatim_last_call = time.time()

    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "limit": limit,
            "countrycodes": "id",
            "addressdetails": 1,
        }
    )
    data = _http_get_json(
        f"{NOMINATIM_BASE}?{params}",
        headers={"Referer": "https://github.com/uangpengiriman"},
    )
    return data if isinstance(data, list) else []


def _pick_best_geocode_candidate(
    candidates: list[dict],
    address: str | None,
    kelurahan: str | None,
    kecamatan: str | None,
    city: str | None,
    name: str | None,
) -> dict:
    if not candidates:
        raise HTTPException(status_code=404, detail="Koordinat tidak ditemukan")
    ranked = sorted(
        candidates,
        key=lambda item: _score_geocode_candidate(item, address, kelurahan, kecamatan, city, name),
        reverse=True,
    )
    best = ranked[0]
    best_score = _score_geocode_candidate(best, address, kelurahan, kecamatan, city, name)
    if best_score < -100:
        raise HTTPException(
            status_code=404,
            detail=(
                "Koordinat tidak yakin ditemukan. Perjelas alamat/kota, "
                "atau geser titik langsung di peta."
            ),
        )
    return best


def _google_geocode_address(
    address: str | None, kelurahan: str | None = None, kecamatan: str | None = None, city: str | None = None, name: str | None = None
) -> tuple[float, float]:
    parts = [p for p in [address, kelurahan, kecamatan, city, _province_for_city(city), "Indonesia"] if p and p.strip()]
    if name and not address:
        parts.insert(0, name)
    query = ", ".join(parts)
    params = urllib.parse.urlencode(
        {
            "address": query,
            "key": settings.google_maps_api_key,
            "region": "id",
            "language": "id",
        }
    )
    data = _http_get_json(f"{GOOGLE_GEOCODE_BASE}?{params}")
    if not isinstance(data, dict) or data.get("status") not in {"OK", "ZERO_RESULTS"}:
        raise HTTPException(status_code=502, detail="Layanan geocode Google gagal")
    results = data.get("results") or []
    if not results:
        raise HTTPException(status_code=404, detail=f"Koordinat tidak ditemukan untuk: {query}")

    city_n = _normalize_text(city)

    def google_score(item: dict) -> float:
        formatted = item.get("formatted_address") or ""
        score = 0.0
        if _admin_city_matches(formatted, city):
            score += 120
        if _admin_city_conflicts(formatted, city):
            score -= 250
        for component in item.get("address_components") or []:
            names = " ".join(component.get("long_name", "")).lower()
            if city_n and city_n in names:
                score += 40
        return score

    best = max(results, key=google_score)
    if city_n and google_score(best) < -100:
        raise HTTPException(
            status_code=404,
            detail="Koordinat Google tidak cocok dengan kota. Geser titik di peta.",
        )
    location = best["geometry"]["location"]
    return float(location["lat"]), float(location["lng"])


def _is_valid_coord(lat: float, lng: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lng <= 180


def _extract_coords_from_text(text: str) -> tuple[float, float] | None:
    decoded = urllib.parse.unquote(text)
    patterns = [
        r"[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"[?&]query=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"[?&]ll=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"[?&]center=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)",
        r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
        r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,\d+(?:\.\d+)?z)?",
        r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, decoded, flags=re.IGNORECASE)
        if not match:
            continue
        lat = float(match.group(1))
        lng = float(match.group(2))
        if _is_valid_coord(lat, lng):
            return lat, lng
    return None


def _extract_url_from_text(text: str) -> str | None:
    match = re.search(r"https?://[^\s<>\"']+", text)
    return match.group(0) if match else None


def _resolve_maps_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.geturl()
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location")
        if location and exc.code in {301, 302, 303, 307, 308}:
            return urllib.parse.urljoin(url, location)
        raise HTTPException(
            status_code=400,
            detail="Link share lokasi tidak bisa dibuka. Coba salin link penuh dari Google Maps.",
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gagal membuka link share lokasi. Periksa koneksi internet.",
        ) from exc


def parse_coords_from_share(text: str) -> tuple[float, float]:
    """Ambil koordinat dari teks/link share lokasi WhatsApp atau Google Maps."""
    raw = (text or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Link atau koordinat kosong.")

    coords = _extract_coords_from_text(raw)
    if coords:
        return coords

    url = _extract_url_from_text(raw) or (raw if raw.startswith("http") else None)
    if url:
        final_url = _resolve_maps_url(url)
        coords = _extract_coords_from_text(final_url)
        if coords:
            return coords

    raise HTTPException(
        status_code=400,
        detail=(
            "Format share lokasi tidak dikenali. Tempel link Google Maps dari WhatsApp "
            "atau koordinat lat, lng."
        ),
    )


def geocode_address(address: str | None, kelurahan: str | None = None, kecamatan: str | None = None, city: str | None = None, name: str | None = None) -> tuple[float, float]:
    if not (address or name or city or kelurahan or kecamatan):
        raise HTTPException(status_code=400, detail="Alamat kosong, tidak bisa geocode")

    if settings.google_maps_api_key:
        try:
            return _google_geocode_address(address, kelurahan, kecamatan, city, name)
        except HTTPException as exc:
            if exc.status_code not in {404, 502}:
                raise

    candidates_by_key: dict[str, dict] = {}
    for query in _geocode_query_variants(address, kelurahan, kecamatan, city, name):
        for item in _nominatim_search(query):
            key = f"{item.get('osm_type')}:{item.get('osm_id')}"
            candidates_by_key.setdefault(key, item)

    if not candidates_by_key:
        raise HTTPException(
            status_code=404,
            detail="Koordinat tidak ditemukan. Perjelas alamat/kota atau geser titik di peta.",
        )

    best = _pick_best_geocode_candidate(
        list(candidates_by_key.values()), address, kelurahan, kecamatan, city, name
    )
    return float(best["lat"]), float(best["lon"])


def _google_route_metrics(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict[str, float | None] | None:
    """Ambil jarak/durasi/tarif tol dari Google Routes API (sekali per pasangan koordinat)."""
    if not settings.google_maps_api_key:
        return None

    payload = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
        "travelMode": "DRIVE",
        "extraComputations": ["TOLLS"],
        "routeModifiers": {"tollPasses": []},
    }
    req = urllib.request.Request(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_maps_api_key,
            "X-Goog-FieldMask": "routes.travelAdvisory.tollInfo,routes.distanceMeters,routes.duration",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    routes = data.get("routes") or []
    if not routes:
        return None

    route0 = routes[0]
    distance_m = route0.get("distanceMeters")
    distance_km = round(float(distance_m) / 1000, 2) if distance_m is not None else None

    duration_min = None
    duration_raw = route0.get("duration")  # e.g. "3345s"
    if isinstance(duration_raw, str) and duration_raw.endswith("s"):
        try:
            duration_min = round(float(duration_raw[:-1]) / 60, 1)
        except ValueError:
            duration_min = None

    toll_idr = 0.0
    toll_info = route0.get("travelAdvisory", {}).get("tollInfo", {}) or {}
    money = toll_info.get("estimatedPrice") or []
    if money:
        total = 0.0
        for entry in money:
            units = float(entry.get("units") or 0)
            nanos = float(entry.get("nanos") or 0) / 1_000_000_000
            total += units + nanos
        toll_idr = round(total, 0)

    return {
        "distance_km": distance_km,
        "duration_min": duration_min,
        "toll_idr": toll_idr,
    }


@lru_cache(maxsize=256)
def _google_route_metrics_cached(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> tuple[float | None, float | None, float | None]:
    metrics = _google_route_metrics(origin_lat, origin_lng, dest_lat, dest_lng)
    if not metrics:
        return (None, None, None)
    return (
        metrics.get("distance_km"),
        metrics.get("duration_min"),
        metrics.get("toll_idr"),
    )


def _google_toll_idr(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> float | None:
    """Kompatibilitas: tarif tol Google (None jika API gagal / key kosong)."""
    if not settings.google_maps_api_key:
        return None
    _dist, _dur, toll = _google_route_metrics_cached(
        round(origin_lat, 5),
        round(origin_lng, 5),
        round(dest_lat, 5),
        round(dest_lng, 5),
    )
    return toll


def _driving_distance(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    *,
    provider: str = "osrm",
) -> dict[str, float | str]:
    """Jarak berkendara gudang→customer (rute langsung, tanpa waypoint gerbang).

    provider:
      - ``osrm`` / ``osrm_direct``: OSRM rute langsung (gratis, mendekati Google Maps)
      - ``google``: Google Routes API (wajib API key)
    """
    provider_key = (provider or "osrm").strip().lower()
    if provider_key == "google":
        if not settings.google_maps_api_key:
            raise HTTPException(
                status_code=400,
                detail="GOOGLE_MAPS_API_KEY belum dikonfigurasi di server.",
            )
        g_dist, g_dur, _toll = _google_route_metrics_cached(
            round(origin_lat, 5),
            round(origin_lng, 5),
            round(dest_lat, 5),
            round(dest_lng, 5),
        )
        if g_dist is None or g_dist <= 0:
            raise HTTPException(
                status_code=400,
                detail="Gagal menghitung jarak via Google Maps. Coba lagi atau pakai OSRM langsung.",
            )
        return {
            "distance_km": float(g_dist),
            "duration_min": float(g_dur) if g_dur is not None else 0.0,
            "source": "google",
        }

    # osrm / osrm_direct / direct → rute OSRM tanpa waypoint
    dist, dur, _geom = _osrm_route_fast(origin_lat, origin_lng, dest_lat, dest_lng, None)
    source = "osrm_direct" if provider_key in ("osrm_direct", "direct") else "osrm"
    return {
        "distance_km": float(dist),
        "duration_min": float(dur),
        "source": source,
    }


def _driving_distance_prefer_google(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict[str, float | str]:
    """Deprecated alias — default sekarang OSRM; Google hanya jika diminta eksplisit."""
    return _driving_distance(origin_lat, origin_lng, dest_lat, dest_lng, provider="osrm")


def _is_toll_step(step: dict) -> bool:
    name = step.get("name", "").lower()
    ref = step.get("ref", "").lower()
    
    if step.get("mode") == "ferry" or step.get("maneuver", {}).get("type") == "ferry":
        return True
    if _road_looks_like_ferry(name) or _road_looks_like_ferry(ref):
        return True
        
    if "tol " in name or name.startswith("tol") or "toll" in name:
        return True
    if "tol " in ref or ref.startswith("tol") or "toll" in ref:
        return True
    for inter in step.get("intersections", []):
        if "toll" in inter.get("classes", []):
            return True
    return False


def _step_display_name(step: dict) -> str:
    name = (step.get("name") or "").strip()
    ref = (step.get("ref") or "").strip()
    
    if step.get("mode") == "ferry" or step.get("maneuver", {}).get("type") == "ferry":
        return name or "Penyeberangan Ferry"
        
    if name and name.lower() not in ("jalan tol", "toll road"):
        return name
    if ref:
        return ref
    return name or "Jalan Tol"


def extract_toll_roads_from_route(route: dict) -> list[dict]:
    """Ruas jalan tol yang benar-benar dilalui rute (dari langkah OSRM)."""
    items: list[dict] = []
    seen: set[str] = set()

    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            if not _is_toll_step(step):
                continue
            label = _step_display_name(step)
            norm = label.lower()
            if norm in seen:
                continue
            seen.add(norm)

            geom = step.get("geometry")
            step_geom = geom.get("coordinates") if isinstance(geom, dict) else []
            lat: float | None = None
            lng: float | None = None
            geometry: list[list[float]] = []
            if step_geom:
                geometry = [[pt[1], pt[0]] for pt in step_geom]
                mid = step_geom[len(step_geom) // 2]
                lng, lat = float(mid[0]), float(mid[1])
            else:
                loc = step.get("maneuver", {}).get("location")
                if loc:
                    lng, lat = float(loc[0]), float(loc[1])
                    geometry = [[lat, lng]]

            if lat is None or lng is None:
                continue

            items.append(
                {
                    "name": label,
                    "latitude": lat,
                    "longitude": lng,
                    "geometry": geometry,
                }
            )

    return items


def _route_uses_toll(route: dict) -> bool:
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            if _is_toll_step(step):
                return True
    return False


def _osrm_route_geometry(osrm_route: dict) -> list[list[float]]:
    coords = osrm_route["geometry"]["coordinates"]
    return [[lat, lng] for lng, lat in coords]


def _estimate_toll_for_osrm_route(
    osrm_route: dict,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    sections: list[dict],
    gate_context: dict | None,
    *,
    force_toll: bool,
) -> dict:
    distance_km = round(float(osrm_route["distance"]) / 1000, 2)
    duration_min = round(float(osrm_route["duration"]) / 60, 1)
    toll_roads = extract_toll_roads_from_route(osrm_route)
    route_toll_names = [r["name"] for r in toll_roads if r.get("name")]
    route_toll_items = toll_roads
    uses_toll = _route_uses_toll(osrm_route)

    google_toll = _google_toll_idr(origin_lat, origin_lng, dest_lat, dest_lng)

    toll_breakdown: list[dict] = []
    toll_source = "none"

    bpjt_result: dict | None = None
    if (uses_toll or force_toll) and gate_context:
        bpjt_result = estimate_toll_bpjt_breakdown(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            gate_context.get("gates") or [],
            gate_context.get("fares") or [],
            golongan_code="II",
            distance_km=distance_km,
            route_toll_roads=route_toll_items,
            sections=sections,
        )

    if bpjt_result and bpjt_result.get("segments"):
        one_way = bpjt_result["one_way_idr"]
        gate_desc = bpjt_result["description"]
        toll_idr = one_way * 2
        toll_is_estimate = False
        toll_breakdown = bpjt_result["segments"]
        toll_source = (
            "route"
            if toll_breakdown and all(s.get("source") == "route" for s in toll_breakdown)
            else "bpjt"
        )
        toll_note = f"{TOLL_NOTE_BPJT} {gate_desc}."
    elif google_toll and google_toll > 0:
        # Referensi Google tetap bisa dipakai saat refresh otomatis
        # (user bisa kosongkan lagi jika tidak sesuai).
        toll_idr = google_toll * 2
        toll_is_estimate = False
        toll_source = "google"
        toll_note = "Tarif tol Pulang-Pergi dari Google Maps (Golongan II/III). Kendaraan Gol IV/V disesuaikan proporsional."
        toll_breakdown = [
            {
                "source": "google",
                "section_name": "Google Maps",
                "entry_gate_code": None,
                "entry_gate_name": None,
                "exit_gate_code": None,
                "exit_gate_name": None,
                "detail": "Estimasi tarif tol dari Google Maps",
                "weight_pct": None,
                "one_way_idr": google_toll,
                "round_trip_idr": google_toll * 2,
            }
        ]
    elif not uses_toll and not force_toll:
        toll_idr = 0.0
        toll_is_estimate = True
        toll_source = "none"
        toll_note = (
            "Rute dari Google Maps tidak melewati jalan tol."
            if google_toll is not None
            else "Rute tidak melewati jalan tol."
        )
        toll_breakdown = []
    else:
        # uses_toll atau force_toll, tanpa hasil BPJT/Google yang valid
        if route_toll_items:
            route_only = breakdown_from_route_sections_only(
                route_toll_items, sections, "II"
            )
            if route_only:
                toll_idr = route_only["one_way_idr"] * 2
                toll_is_estimate = True
                toll_source = "route"
                toll_breakdown = route_only["segments"]
                toll_note = (
                    "Tarif acuan ruas BPJT untuk ruas tol yang dilalui di peta. "
                    "(Dikali 2 untuk Pulang-Pergi.)"
                )
            else:
                toll_idr = 0.0
                toll_is_estimate = True
                toll_source = "route"
                toll_breakdown = [
                    {
                        "source": "route",
                        "section_name": name,
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
                    for name in route_toll_names
                ]
                toll_note = (
                    "Ruas tol di peta belum terpetakan ke master BPJT: "
                    + ", ".join(route_toll_names)
                    + ". Isi matriks gerbang di menu Gerbang Tol."
                )
        else:
            section_result = jabodetabek_toll_breakdown(distance_km, "II", sections)
            toll_idr = section_result["one_way_idr"] * 2
            toll_is_estimate = True
            toll_source = "section"
            toll_breakdown = section_result["segments"]
            note_suffix = (
                " (Asumsi lewat tol manual, dikali 2 untuk Pulang-Pergi)."
                if force_toll
                else " (Dikali 2 untuk Pulang-Pergi)."
            )
            toll_note = TOLL_NOTE_JABODETABEK + note_suffix

    return {
        "distance_km": distance_km,
        "duration_min": duration_min,
        "toll_idr": toll_idr,
        "toll_is_estimate": toll_is_estimate,
        "toll_note": toll_note,
        "toll_source": toll_source,
        "toll_breakdown": toll_breakdown,
        "toll_roads": toll_roads,
        "uses_toll": uses_toll,
    }


def _pick_cheapest_toll_route_index(
    estimates: list[dict],
    *,
    force_toll: bool,
    prefer_cheapest_toll: bool,
) -> int:
    """Pilih alternatif OSRM: default rute tercepat (index 0).

    Mode tol termurah hanya dipakai jika alternatif masih masuk akal (bukan muter jauh)
    dan hemat tol cukup signifikan dibanding rute tercepat.
    """
    if not estimates:
        return 0

    baseline_idx = 0
    baseline = estimates[baseline_idx]
    max_dist = baseline["distance_km"] * 1.15 + 3.0
    max_dur = baseline["duration_min"] + 20.0

    toll_indices = [idx for idx, est in enumerate(estimates) if est["uses_toll"]]

    def within_reasonable_detour(idx: int) -> bool:
        est = estimates[idx]
        return est["distance_km"] <= max_dist and est["duration_min"] <= max_dur

    def toll_sort_key(idx: int) -> tuple:
        est = estimates[idx]
        return (est["toll_idr"], est["distance_km"], est["duration_min"])

    if force_toll and toll_indices and not baseline["uses_toll"]:
        pool = [idx for idx in toll_indices if within_reasonable_detour(idx)] or toll_indices
        return min(pool, key=toll_sort_key)

    if not prefer_cheapest_toll:
        return baseline_idx

    if not toll_indices or len(toll_indices) <= 1:
        return baseline_idx

    if not baseline["uses_toll"]:
        return baseline_idx

    candidates = [idx for idx in toll_indices if within_reasonable_detour(idx)]
    if not candidates:
        return baseline_idx

    baseline_toll = float(baseline["toll_idr"] or 0)
    best_idx = min(candidates, key=toll_sort_key)
    best_toll = float(estimates[best_idx]["toll_idr"] or 0)
    min_savings = max(5000.0, baseline_toll * 0.05)
    if best_idx != baseline_idx and best_toll + min_savings < baseline_toll:
        return best_idx
    return baseline_idx


def _osrm_leg_fast(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> tuple[float, float, list[list[float]]]:
    """Satu segmen OSRM ringan — tanpa alternatif & tanpa langkah (untuk koridor tol)."""
    return _osrm_route_fast_impl(
        round(origin_lat, 4),
        round(origin_lng, 4),
        round(dest_lat, 4),
        round(dest_lng, 4),
        (),
    )


@lru_cache(maxsize=128)
def _osrm_route_fast_impl(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    waypoints: tuple[tuple[float, float], ...],
) -> tuple[float, float, tuple[tuple[float, float], ...]]:
    """Satu request OSRM (boleh multi-waypoint), cached per koordinat."""
    parts = [f"{origin_lng},{origin_lat}"]
    for wp_lat, wp_lng in waypoints:
        parts.append(f"{wp_lng},{wp_lat}")
    parts.append(f"{dest_lng},{dest_lat}")
    coord_str = ";".join(parts)
    url = (
        f"{osrm_base_url()}/{coord_str}"
        f"?overview=full&geometries=geojson&steps=false&alternatives=0"
    )
    data = _http_get_json(url)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise HTTPException(status_code=400, detail="Rute tidak ditemukan antara gudang dan customer")
    route = data["routes"][0]
    distance_km = round(float(route["distance"]) / 1000, 2)
    duration_min = round(float(route["duration"]) / 60, 1)
    geometry = tuple(
        (float(lat), float(lng))
        for lng, lat in route["geometry"]["coordinates"]
    )
    return distance_km, duration_min, geometry


def _osrm_route_fast(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    waypoints: list[tuple[float, float]] | None = None,
) -> tuple[float, float, list[list[float]]]:
    wp_key = tuple(
        (round(lat, 4), round(lng, 4)) for lat, lng in (waypoints or [])
    )
    distance_km, duration_min, geometry = _osrm_route_fast_impl(
        round(origin_lat, 4),
        round(origin_lng, 4),
        round(dest_lat, 4),
        round(dest_lng, 4),
        wp_key,
    )
    return distance_km, duration_min, [[lat, lng] for lat, lng in geometry]


def sequential_driving_km(points: list[tuple[float, float]]) -> float | None:
    """Jarak tempuh berurutan: titik 1 → 2 → 3 → … (satu request OSRM)."""
    if len(points) < 2:
        return None
    try:
        km, _, _ = _osrm_route_fast(
            points[0][0],
            points[0][1],
            points[-1][0],
            points[-1][1],
            waypoints=list(points[1:-1]) if len(points) > 2 else None,
        )
        return float(km)
    except HTTPException:
        return None


def calculate_route_chained(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    waypoints: list[tuple[float, float]],
    sections: list[dict] | None = None,
    force_toll: bool = False,
    gate_context: dict | None = None,
    *,
    prefer_corridor: bool = False,
) -> tuple[dict, bool]:
    """Koridor tol: satu request OSRM multi-waypoint (bukan N request berurutan).

    prefer_corridor=True: pakai jalur via gerbang tol meskipun lebih jauh
    (untuk ruas yang dipilih manual user).
    """
    if not waypoints:
        route = calculate_route(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            sections=sections,
            force_toll=force_toll,
            gate_context=gate_context,
            prefer_cheapest_toll=False,
            waypoints=None,
        )
        return route, False

    direct_hav = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    # Manual: toleransi lebih longgar agar jalur tetap lewat gerbang tol.
    if prefer_corridor:
        max_km = max(direct_hav * 3.5, direct_hav + 45.0)
    else:
        max_km = max(direct_hav * 1.55, direct_hav + 12.0)

    try:
        corridor_dist, corridor_dur, corridor_geom = _osrm_route_fast(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            waypoints,
        )
    except HTTPException:
        corridor_dist, corridor_dur, corridor_geom = _osrm_route_fast(
            origin_lat, origin_lng, dest_lat, dest_lng, None
        )
        return {
            "distance_km": corridor_dist,
            "duration_min": corridor_dur,
            "geometry": corridor_geom,
            "toll_roads": [],
            "toll_idr": 0.0,
            "toll_is_estimate": True,
            "toll_note": "",
            "toll_source": "none",
            "toll_breakdown": [],
        }, False

    # Ruas manual: tetap pakai koridor gerbang (ikuti jalur tol), jangan fallback lurus.
    if corridor_dist > max_km and not prefer_corridor:
        direct_dist, direct_dur, direct_geom = _osrm_route_fast(
            origin_lat, origin_lng, dest_lat, dest_lng, None
        )
        return {
            "distance_km": direct_dist,
            "duration_min": direct_dur,
            "geometry": direct_geom,
            "toll_roads": [],
            "toll_idr": 0.0,
            "toll_is_estimate": True,
            "toll_note": "",
            "toll_source": "none",
            "toll_breakdown": [],
        }, False

    return {
        "distance_km": corridor_dist,
        "duration_min": corridor_dur,
        "geometry": corridor_geom,
        "toll_roads": [],
        "toll_idr": 0.0,
        "toll_is_estimate": True,
        "toll_note": "",
        "toll_source": "none",
        "toll_breakdown": [],
    }, True


def build_toll_road_overlays(segments: list[dict], gates: list[dict]) -> list[dict]:
    """Overlay ruas tol di peta — geometri mengikuti jalan (OSRM), bukan garis lurus."""
    from app.toll_gate_service import (
        segments_need_jorr_jagorawi_transfer,
        toll_segment_map_geometry,
    )

    # Hanya Jagorawi yang memotong JORR di Taman Mini.
    # Japek harus tetap sampai Cikunir (jangan dipotong di TMII — bikin kotak + km berlebih).
    clip_jorr_at_tmii = segments_need_jorr_jagorawi_transfer(segments)

    roads: list[dict] = []
    for seg in segments:
        anchors = toll_segment_map_geometry(
            seg,
            gates,
            clip_jorr_at_transfer=clip_jorr_at_tmii,
        )
        geom = list(anchors)
        if len(anchors) >= 2:
            # Jahit per pasangan gerbang berurutan — lebih stabil di ring JORR
            # daripada satu request multi-waypoint yang sering keluar tol.
            stitched: list[list[float]] = []
            try:
                for i in range(len(anchors) - 1):
                    start = anchors[i]
                    end = anchors[i + 1]
                    _, _, road = _osrm_route_fast(
                        start[0],
                        start[1],
                        end[0],
                        end[1],
                        None,
                    )
                    if len(road) < 2:
                        continue
                    if (
                        stitched
                        and abs(stitched[-1][0] - road[0][0]) < 1e-5
                        and abs(stitched[-1][1] - road[0][1]) < 1e-5
                    ):
                        stitched.extend(road[1:])
                    else:
                        stitched.extend(road)
                if len(stitched) > 2:
                    geom = stitched
            except HTTPException:
                try:
                    start = anchors[0]
                    end = anchors[-1]
                    middles = anchors[1:-1] if len(anchors) > 2 else None
                    _, _, road = _osrm_route_fast(
                        start[0],
                        start[1],
                        end[0],
                        end[1],
                        middles,
                    )
                    if len(road) > 2:
                        geom = road
                except HTTPException:
                    pass
        roads.append(
            {
                "name": seg.get("section_name")
                or (
                    f"{seg.get('entry_gate_name') or seg.get('entry_gate_code') or '?'} → "
                    f"{seg.get('exit_gate_name') or seg.get('exit_gate_code') or '?'}"
                ),
                "latitude": geom[0][0] if geom else None,
                "longitude": geom[0][1] if geom else None,
                "geometry": geom,
            }
        )
    return roads


def calculate_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    sections: list[dict] | None = None,
    force_toll: bool = False,
    gate_context: dict | None = None,
    prefer_cheapest_toll: bool = False,
    waypoints: list[tuple[float, float]] | None = None,
    distance_provider: str = "osrm",
) -> dict:
    coord_parts = [f"{origin_lng},{origin_lat}"]
    if waypoints:
        for wp_lat, wp_lng in waypoints:
            coord_parts.append(f"{wp_lng},{wp_lat}")
    coord_parts.append(f"{dest_lng},{dest_lat}")
    coord_str = ";".join(coord_parts)
    alt_count = 1 if waypoints or not prefer_cheapest_toll else 3
    url = (
        f"{osrm_base_url()}/{coord_str}?overview=full&geometries=geojson&steps=true"
        f"&alternatives={alt_count}"
    )
    data = _http_get_json(url)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise HTTPException(status_code=400, detail="Rute tidak ditemukan antara gudang dan customer")

    sections = sections or _default_sections_from_settings()
    routes = data["routes"]
    estimates = [
        _estimate_toll_for_osrm_route(
            route,
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            sections,
            gate_context,
            force_toll=force_toll,
        )
        for route in routes
    ]

    selected_idx = _pick_cheapest_toll_route_index(
        estimates,
        force_toll=force_toll,
        prefer_cheapest_toll=prefer_cheapest_toll,
    )
    selected_route = routes[selected_idx]
    result = dict(estimates[selected_idx])
    result.pop("uses_toll", None)
    result["geometry"] = _osrm_route_geometry(selected_route)

    toll_indices = [idx for idx, est in enumerate(estimates) if est["uses_toll"]]
    result["alternatives_compared"] = len(routes)
    result["route_selection"] = None
    result["toll_savings_idr"] = None

    if len(toll_indices) > 1 and selected_idx != 0:
        default_toll = estimates[0]["toll_idr"] if estimates[0]["uses_toll"] else None
        selected_toll = estimates[selected_idx]["toll_idr"]
        result["route_selection"] = "tol_termurah"
        if default_toll is not None and selected_toll < default_toll:
            result["toll_savings_idr"] = round(default_toll - selected_toll, 0)

    if result.get("route_selection") == "tol_termurah":
        savings = result.get("toll_savings_idr")
        savings_text = (
            f" Hemat {int(savings):,} dibanding rute tercepat.".replace(",", ".")
            if savings and savings > 0
            else ""
        )
        result["toll_note"] = (
            f"Dipilih rute tol termurah dari {len(routes)} alternatif OSRM.{savings_text} "
            + (result.get("toll_note") or "")
        )

    # Simpan jarak rute OSRM + jarak langsung untuk perbandingan di UI
    route_km = float(result.get("distance_km") or 0)
    route_dur = float(result.get("duration_min") or 0)
    result["distance_km_route"] = route_km
    result["duration_min_route"] = route_dur
    try:
        direct = _driving_distance(
            origin_lat, origin_lng, dest_lat, dest_lng, provider="osrm_direct"
        )
        result["distance_km_direct"] = float(direct["distance_km"])
        result["duration_min_direct"] = float(direct["duration_min"] or 0)
    except Exception:
        result["distance_km_direct"] = route_km
        result["duration_min_direct"] = route_dur

    provider = (distance_provider or "osrm").strip().lower()
    if provider in ("google", "osrm_direct", "direct"):
        driving = _driving_distance(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            provider="google" if provider == "google" else "osrm_direct",
        )
        result["distance_km"] = driving["distance_km"]
        if driving["duration_min"]:
            result["duration_min"] = driving["duration_min"]
        result["distance_source"] = driving["source"]
        if driving["source"] == "google":
            result["distance_km_direct"] = float(driving["distance_km"])
            result["duration_min_direct"] = float(driving["duration_min"] or 0)
        note = result.get("toll_note") or ""
        if driving["source"] == "google":
            label = f"Jarak BBM dari Google Maps ({driving['distance_km']} km)."
        else:
            label = (
                f"Jarak BBM dari OSRM langsung ({driving['distance_km']} km), "
                "mendekati Google Maps."
            )
        result["toll_note"] = f"{label} {note}".strip()
    else:
        result["distance_source"] = "osrm"
        result["distance_km"] = route_km
        result["duration_min"] = route_dur

    return result
