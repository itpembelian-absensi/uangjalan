from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException

from app.core.config import settings

USER_AGENT = "UangPengiriman/1.0"
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODE_BASE = "https://maps.googleapis.com/maps/api/geocode/json"

TOLL_VEHICLE_ORDER = ("grandmax", "engkle", "double", "fuso", "tronton")

VEHICLE_TOLL_CLASS: dict[str, dict[str, str]] = {
    "grandmax": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "engkle": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "double": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "fuso": {"golongan_code": "II", "golongan": "II", "gandar": "2 gandar"},
    "tronton": {"golongan_code": "III", "golongan": "III", "gandar": "3 gandar"},
}

TOLL_NOTE_JABODETABEK = (
    "Estimasi berdasarkan acuan ruas tol Jabodetabek per golongan kendaraan. "
    "Golongan II & III tarif sama; Golongan IV & V tarif lebih tinggi. "
    "Tarif aktual bergantung gerbang masuk/keluar — rujukan: Kalkulator Jasa Marga / BPJT Info Tol."
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


def _normalize_vehicle_key(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "")


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


def _http_get_json(url: str, headers: dict | None = None) -> object:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Layanan peta gagal ({e.code})") from e
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail="Tidak dapat terhubung ke layanan peta/rute") from e


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


def _nominatim_search(query: str, limit: int = 8) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "limit": limit,
            "countrycodes": "id",
            "addressdetails": 1,
        }
    )
    data = _http_get_json(f"{NOMINATIM_BASE}?{params}")
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
        r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:,\d+(?:\.\d+)?z)?",
        r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",
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


def _google_toll_idr(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> float | None:
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
    toll_info = routes[0].get("travelAdvisory", {}).get("tollInfo", {})
    money = toll_info.get("estimatedPrice") or []
    if not money:
        return 0.0
    total = 0.0
    for entry in money:
        units = float(entry.get("units") or 0)
        nanos = float(entry.get("nanos") or 0) / 1_000_000_000
        total += units + nanos
    return round(total, 0)


def calculate_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    sections: list[dict] | None = None,
    force_toll: bool = False,
) -> dict:
    url = f"{OSRM_BASE}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=full&geometries=geojson&steps=true&alternatives=3"
    data = _http_get_json(url)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise HTTPException(status_code=400, detail="Rute tidak ditemukan antara gudang dan customer")

    def check_uses_toll(r: dict) -> bool:
        for leg in r.get("legs", []):
            for step in leg.get("steps", []):
                name = step.get("name", "").lower()
                ref = step.get("ref", "").lower()
                if "tol " in name or name.startswith("tol") or "toll" in name:
                    return True
                if "tol " in ref or ref.startswith("tol") or "toll" in ref:
                    return True
                for inter in step.get("intersections", []):
                    if "toll" in inter.get("classes", []):
                        return True
        return False

    selected_route = data["routes"][0]
    uses_toll = check_uses_toll(selected_route)

    if force_toll and not uses_toll:
        for r in data["routes"][1:]:
            if check_uses_toll(r):
                selected_route = r
                uses_toll = True
                break

    distance_km = round(float(selected_route["distance"]) / 1000, 2)
    duration_min = round(float(selected_route["duration"]) / 60, 1)
    coords = selected_route["geometry"]["coordinates"]
    geometry = [[lat, lng] for lng, lat in coords]

    sections = sections or _default_sections_from_settings()
    google_toll = _google_toll_idr(origin_lat, origin_lng, dest_lat, dest_lng)
    
    if google_toll and google_toll > 0:
        toll_idr = google_toll * 2
        toll_is_estimate = False
        toll_note = "Tarif tol Pulang-Pergi dari Google Maps (Golongan II/III). Kendaraan Gol IV/V disesuaikan proporsional."
    elif google_toll is not None and not force_toll:
        toll_idr = 0.0
        toll_is_estimate = True
        toll_note = "Rute dari Google Maps tidak melewati jalan tol."
    else:
        if uses_toll or force_toll:
            toll_idr = estimate_jabodetabek_toll(distance_km, "II", sections) * 2
            toll_is_estimate = True
            note_suffix = " (Asumsi lewat tol manual, dikali 2 untuk Pulang-Pergi)." if force_toll else " (Dikali 2 untuk Pulang-Pergi)."
            toll_note = TOLL_NOTE_JABODETABEK + note_suffix
        else:
            toll_idr = 0.0
            toll_is_estimate = True
            toll_note = "Rute tidak melewati jalan tol."

    return {
        "distance_km": distance_km,
        "duration_min": duration_min,
        "toll_idr": toll_idr,
        "toll_is_estimate": toll_is_estimate,
        "toll_note": toll_note,
        "geometry": geometry,
    }
