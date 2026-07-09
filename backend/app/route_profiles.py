"""Preset koridor tol Jabodetabek — ruas tol per skema rute."""

from __future__ import annotations

from app.toll_gate_service import _normalize_toll_text


ROUTE_PROFILES: list[dict] = [
    {
        "key": "auto",
        "label": "Otomatis (rute tercepat OSRM)",
        "description": "Rute tercepat dari OSRM. Alternatif tol lebih murah dipakai hanya jika jarak/waktu masih wajar.",
        "steps": [],
    },
    {
        "key": "manual",
        "label": "Manual (atur ruas sendiri)",
        "description": "Tambah atau ubah ruas tol satu per satu di tabel gerbang.",
        "steps": None,
    },
    {
        "key": "dalam_priok_japek",
        "label": "Lingkar Dalam via Priok → Japek",
        "description": "Soedijatmo, tol Priok/Pelabuhan, lanjut Jakarta–Cikampek.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["priok", "pelabuhan", "aksestanjung", "tanjungpriok"]},
            {"japek": True},
        ],
    },
    {
        "key": "dalam_ctc_japek",
        "label": "Lingkar Dalam (CTC) → Japek",
        "description": "Soedijatmo, Cawang–Tomang–Pluit (CTC), lanjut Jakarta–Cikampek.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["ctc", "tomang", "cawangtomangpluit"]},
            {"japek": True},
        ],
    },
    {
        "key": "luar_jorr_japek",
        "label": "Lingkar Luar (JORR) → Japek",
        "description": (
            "Soedijatmo, JORR timur (Cakung–Cilincing) atau JORR barat/utara, "
            "lanjut Jakarta–Cikampek — otomatis sesuai arah tujuan."
        ),
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"jorr": True},
            {"japek": True},
        ],
    },
    {
        "key": "dalam_ctc_bogor",
        "label": "Lingkar Dalam (CTC) → Bogor",
        "description": "Soedijatmo, CTC, Jakarta–Bogor–Ciawi. Otomatis jadi Japek jika tujuan timur.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["ctc", "tomang", "cawangtomangpluit"]},
            {"patterns": ["jakartabogorciawi", "bogorciawi"]},
        ],
    },
    {
        "key": "dalam_priok_bogor",
        "label": "Lingkar Dalam via Priok → Bogor",
        "description": "Soedijatmo, tol Priok/Pelabuhan, Jakarta–Bogor–Ciawi. Otomatis jadi Japek jika tujuan timur.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["priok", "pelabuhan", "aksestanjung", "tanjungpriok"]},
            {"patterns": ["jakartabogorciawi", "bogorciawi"]},
        ],
    },
    {
        "key": "dalam_ctc_japek_padalarang",
        "label": "Lingkar Dalam (CTC) → Japek → Padalarang",
        "description": "Soedijatmo, CTC, Jakarta–Cikampek, Cipularang (Padalarang).",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["ctc", "tomang", "cawangtomangpluit"]},
            {"japek": True},
            {"cipularang": True},
        ],
    },
    {
        "key": "dalam_ctc_japek_bandung",
        "label": "Lingkar Dalam (CTC) → Japek → Bandung",
        "description": "Soedijatmo, CTC, Jakarta–Cikampek, Cipularang, Padaleunyi (Cileunyi).",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["ctc", "tomang", "cawangtomangpluit"]},
            {"japek": True},
            {"cipularang": True},
            {"padaleunyi": True},
        ],
    },
    {
        "key": "dalam_ctc_japek_tasik",
        "label": "Lingkar Dalam (CTC) → Japek → Tasik",
        "description": "Soedijatmo, CTC, Jakarta–Cikampek, Cipularang, Padaleunyi, Cisumdawu.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["ctc", "tomang", "cawangtomangpluit"]},
            {"japek": True},
            {"cipularang": True},
            {"padaleunyi": True},
            {"cisumdawu": True},
        ],
    },
    {
        "key": "dalam_priok_japek_padalarang",
        "label": "Lingkar Dalam via Priok → Japek → Padalarang",
        "description": "Soedijatmo, tol Priok, Jakarta–Cikampek, Cipularang (Padalarang).",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["priok", "pelabuhan", "aksestanjung", "tanjungpriok"]},
            {"japek": True},
            {"cipularang": True},
        ],
    },
    {
        "key": "dalam_priok_japek_bandung",
        "label": "Lingkar Dalam via Priok → Japek → Bandung",
        "description": "Soedijatmo, tol Priok, Jakarta–Cikampek, Cipularang, Padaleunyi (Cileunyi).",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["priok", "pelabuhan", "aksestanjung", "tanjungpriok"]},
            {"japek": True},
            {"cipularang": True},
            {"padaleunyi": True},
        ],
    },
    {
        "key": "dalam_priok_japek_tasik",
        "label": "Lingkar Dalam via Priok → Japek → Tasik",
        "description": "Soedijatmo, tol Priok, Jakarta–Cikampek, Cipularang, Padaleunyi, Cisumdawu.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"patterns": ["priok", "pelabuhan", "aksestanjung", "tanjungpriok"]},
            {"japek": True},
            {"cipularang": True},
            {"padaleunyi": True},
            {"cisumdawu": True},
        ],
    },
    {
        "key": "luar_jorr_japek_padalarang",
        "label": "Lingkar Luar (JORR) → Japek → Padalarang",
        "description": "Soedijatmo, JORR, Jakarta–Cikampek, Cipularang (Padalarang).",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"jorr": True},
            {"japek": True},
            {"cipularang": True},
        ],
    },
    {
        "key": "luar_jorr_japek_bandung",
        "label": "Lingkar Luar (JORR) → Japek → Bandung",
        "description": "Soedijatmo, JORR, Jakarta–Cikampek, Cipularang, Padaleunyi (Cileunyi).",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"jorr": True},
            {"japek": True},
            {"cipularang": True},
            {"padaleunyi": True},
        ],
    },
    {
        "key": "luar_jorr_japek_tasik",
        "label": "Lingkar Luar (JORR) → Japek → Tasik",
        "description": "Soedijatmo, JORR, Jakarta–Cikampek, Cipularang, Padaleunyi, Cisumdawu.",
        "steps": [
            {"patterns": ["soedijatmo", "sedyatmo"]},
            {"jorr": True},
            {"japek": True},
            {"cipularang": True},
            {"padaleunyi": True},
            {"cisumdawu": True},
        ],
    },
]

_PROFILE_BY_KEY = {p["key"]: p for p in ROUTE_PROFILES}

_PROFILE_EAST_ALIASES = {
    "dalam_ctc_bogor": "dalam_ctc_japek",
    "dalam_priok_bogor": "dalam_priok_japek",
}
_PROFILE_SOUTH_ALIASES = {
    "dalam_ctc_japek": "dalam_ctc_bogor",
    "dalam_priok_japek": "dalam_priok_bogor",
}

_WEST_SUFFIXES = ("_padalarang", "_bandung", "_tasik")
_WEST_SUFFIX_BY_CORRIDOR = {
    "west_padalarang": "_padalarang",
    "west_bandung": "_bandung",
    "tasik": "_tasik",
}


def _split_west_profile_key(profile_key: str) -> tuple[str, str] | None:
    for suffix in _WEST_SUFFIXES:
        if profile_key.endswith(suffix):
            return profile_key[: -len(suffix)], suffix
    return None


def destination_corridor(dest_lat: float, dest_lng: float) -> str:
    """Klasifikasi arah tujuan: east, south, west (Padalarang/Bandung), tasik, inner."""
    if dest_lat <= -7.0 and dest_lng >= 107.5:
        return "tasik"
    if dest_lng >= 107.35 and dest_lat <= -6.72:
        return "west_bandung"
    if dest_lng >= 107.33 and dest_lat <= -6.55:
        return "west_padalarang"
    if dest_lat <= -6.46 and dest_lng < 106.95:
        return "south"
    if dest_lng >= 106.92 or (dest_lng >= 106.88 and dest_lat > -6.42):
        return "east"
    return "inner"


def resolve_effective_profile_key(
    profile_key: str,
    dest_lat: float,
    dest_lng: float,
) -> str:
    corridor = destination_corridor(dest_lat, dest_lng)
    west_parts = _split_west_profile_key(profile_key)
    if west_parts:
        base, _requested = west_parts
        if corridor in ("east", "south", "inner"):
            return base
        return base + _WEST_SUFFIX_BY_CORRIDOR.get(corridor, "_padalarang")

    if corridor == "east" and profile_key in _PROFILE_EAST_ALIASES:
        return _PROFILE_EAST_ALIASES[profile_key]
    if corridor == "south" and profile_key in _PROFILE_SOUTH_ALIASES:
        return _PROFILE_SOUTH_ALIASES[profile_key]
    return profile_key


def _step_is_bogor_only(step: dict) -> bool:
    if step.get("japek"):
        return False
    blob = _normalize_toll_text(" ".join(step.get("patterns") or []))
    return any(k in blob for k in ("bogor", "ciawi", "jakartabogor"))


def _step_is_japek_only(step: dict) -> bool:
    return bool(step.get("japek"))


def list_route_profiles() -> list[dict]:
    return [
        {"key": p["key"], "label": p["label"], "description": p.get("description")}
        for p in ROUTE_PROFILES
        if p["key"] == "auto"
    ]


def _section_text(section: dict) -> str:
    parts = [
        section.get("name") or "",
        section.get("origin_name") or "",
        section.get("destination_name") or "",
    ]
    return _normalize_toll_text(" ".join(parts))


def _find_section_by_patterns(sections: list[dict], patterns: list[str]) -> dict | None:
    for pattern in patterns:
        pat = _normalize_toll_text(pattern)
        if not pat:
            continue
        for section in sections:
            text = _section_text(section)
            if pat in text:
                return section
    return None


def _is_west_corridor(corridor: str) -> bool:
    return corridor in _WEST_SUFFIX_BY_CORRIDOR


def _japek_exit_patterns(dest_lat: float, dest_lng: float) -> list[str]:
    """Prioritas gerbang keluar Japek berdasarkan arah tujuan."""
    corridor = destination_corridor(dest_lat, dest_lng)
    if _is_west_corridor(corridor):
        return ["cikampek", "dawuan", "kalihurip"]
    if corridor == "south":
        return ["ciawi", "bogor", "sentul"]
    if dest_lng > 107.15:
        return ["karawangtimur", "karawangbarat", "cikampek", "dawuan", "kalihurip"]
    if dest_lng > 107.0:
        return ["karawangbarat", "karawangtimur", "cikampek", "dawuan"]
    if dest_lng > 106.98:
        return [
            "cikarangtimur",
            "cikarangbarat",
            "cibitung",
            "cikunir",
            "cikampek",
        ]
    if dest_lng > 106.94 and -6.35 < dest_lat < -6.05:
        return ["cikunir", "cibitung", "bekasitimur", "bekasibarat", "pondokgede"]
    return ["cikunir", "bekasi", "cibitung"]


def _find_japek_section(sections: list[dict], dest_lat: float, dest_lng: float) -> dict | None:
    japek_sections = [
        s
        for s in sections
        if "jakartacikampek" in _section_text(s) and "→" in (s.get("name") or "")
    ]
    if not japek_sections:
        japek_sections = [
            s for s in sections if "jakartacikampek" in _section_text(s)
        ]
    patterns = _japek_exit_patterns(dest_lat, dest_lng)
    for pattern in patterns:
        pat = _normalize_toll_text(pattern)
        for section in japek_sections:
            if pat in _section_text(section):
                return section
    return japek_sections[0] if japek_sections else None


def _cipularang_exit_patterns(dest_lat: float, dest_lng: float) -> list[str]:
    corridor = destination_corridor(dest_lat, dest_lng)
    if corridor == "west_padalarang":
        return ["padalarang", "purbaleunyi"]
    return ["padalarang", "purbaleunyi", "dawuan", "cikampek"]


def _find_cipularang_section(sections: list[dict], dest_lat: float, dest_lng: float) -> dict | None:
    cipularang_sections = [
        s
        for s in sections
        if "cipularang" in _section_text(s) or (
            "cikampek" in _section_text(s) and "padalarang" in _section_text(s)
        )
    ]
    for pattern in _cipularang_exit_patterns(dest_lat, dest_lng):
        pat = _normalize_toll_text(pattern)
        for section in cipularang_sections:
            if pat in _section_text(section):
                return section
    return cipularang_sections[0] if cipularang_sections else None


def _padaleunyi_exit_patterns(dest_lat: float, dest_lng: float) -> list[str]:
    corridor = destination_corridor(dest_lat, dest_lng)
    if corridor == "tasik":
        return ["cileunyi"]
    return ["cileunyi", "pasteur", "buahbatu", "pasirkoja"]


def _find_padaleunyi_section(sections: list[dict], dest_lat: float, dest_lng: float) -> dict | None:
    padaleunyi_sections = [
        s
        for s in sections
        if any(
            k in _section_text(s)
            for k in ("padaleunyi", "purbaleunyi", "padalarangcileunyi")
        )
        or (
            "padalarang" in _section_text(s)
            and "cileunyi" in _section_text(s)
            and "cipularang" not in _section_text(s)
        )
    ]
    for pattern in _padaleunyi_exit_patterns(dest_lat, dest_lng):
        pat = _normalize_toll_text(pattern)
        for section in padaleunyi_sections:
            if pat in _section_text(section):
                return section
    return padaleunyi_sections[0] if padaleunyi_sections else None


def _cisumdawu_exit_patterns(dest_lat: float, dest_lng: float) -> list[str]:
    if dest_lat <= -7.15:
        return ["cisumdawuutama", "paseh", "cisumdawujaya"]
    return ["cisumdawuutama", "paseh", "jatinangor", "cileunyi"]


def _find_cisumdawu_section(sections: list[dict], dest_lat: float, dest_lng: float) -> dict | None:
    cisumdawu_sections = [s for s in sections if "cisumdawu" in _section_text(s)]
    for pattern in _cisumdawu_exit_patterns(dest_lat, dest_lng):
        pat = _normalize_toll_text(pattern)
        for section in cisumdawu_sections:
            if pat in _section_text(section):
                return section
    return cisumdawu_sections[0] if cisumdawu_sections else None


def find_jorr_section_ids(
    sections: list[dict],
    dest_lat: float,
    dest_lng: float,
) -> list[int]:
    """Pilih ruas JORR yang sesuai arah tujuan (timur vs barat/selatan)."""
    corridor = destination_corridor(dest_lat, dest_lng)
    ids: list[int] = []

    if corridor == "east":
        section = _find_section_by_patterns(sections, ["cibungtcilincing", "cilincing"])
        if not section:
            section = _find_section_by_patterns(sections, ["jorrnon", "rorotan", "kebonbawang"])
        if section and section.get("id") is not None:
            return [int(section["id"])]
        return ids

    for patterns in (
        ["jorrw1", "kebonjerukpenjaringan"],
        ["jorrw2", "kebonjerukulujami"],
        ["jorrnon", "rorotan"],
        ["jorrs", "pondokpinang", "tamanmini"],
    ):
        section = _find_section_by_patterns(sections, patterns)
        if section and section.get("id") is not None:
            return [int(section["id"])]
    return ids


def resolve_profile_section_ids(
    profile_key: str,
    sections: list[dict],
    dest_lat: float,
    dest_lng: float,
) -> list[int]:
    effective_key = resolve_effective_profile_key(profile_key, dest_lat, dest_lng)
    profile = _PROFILE_BY_KEY.get(effective_key)
    if not profile or profile.get("steps") is None:
        return []
    if not profile.get("steps"):
        return []

    corridor = destination_corridor(dest_lat, dest_lng)
    ids: list[int] = []
    has_japek = False
    for step in profile["steps"]:
        if _step_is_bogor_only(step) and corridor != "south":
            continue
        if _step_is_japek_only(step) and corridor == "south":
            continue
        if step.get("japek"):
            section = _find_japek_section(sections, dest_lat, dest_lng)
            has_japek = True
        elif step.get("jorr"):
            for sid in find_jorr_section_ids(sections, dest_lat, dest_lng):
                if sid not in ids:
                    ids.append(sid)
            continue
        elif step.get("cipularang"):
            section = _find_cipularang_section(sections, dest_lat, dest_lng)
        elif step.get("padaleunyi"):
            section = _find_padaleunyi_section(sections, dest_lat, dest_lng)
        elif step.get("cisumdawu"):
            section = _find_cisumdawu_section(sections, dest_lat, dest_lng)
        else:
            section = _find_section_by_patterns(sections, step.get("patterns") or [])
        if not section or section.get("id") is None:
            continue
        sid = int(section["id"])
        if sid not in ids:
            ids.append(sid)

    if corridor == "east" and not has_japek:
        japek = _find_japek_section(sections, dest_lat, dest_lng)
        if japek and japek.get("id") is not None:
            sid = int(japek["id"])
            if sid not in ids:
                ids.append(sid)

    if _is_west_corridor(corridor) and not has_japek:
        japek = _find_japek_section(sections, dest_lat, dest_lng)
        if japek and japek.get("id") is not None:
            sid = int(japek["id"])
            if sid not in ids:
                ids.append(sid)

    return ids


def profile_adaptation_note(
    requested_key: str,
    dest_lat: float,
    dest_lng: float,
) -> str | None:
    effective = resolve_effective_profile_key(requested_key, dest_lat, dest_lng)
    if effective == requested_key:
        return None
    req = _PROFILE_BY_KEY.get(requested_key, {})
    eff = _PROFILE_BY_KEY.get(effective, {})
    corridor = destination_corridor(dest_lat, dest_lng)
    if _split_west_profile_key(requested_key):
        if corridor in ("east", "south", "inner"):
            direction = (
                "timur (Japek)"
                if corridor == "east"
                else "selatan (Bogor)"
                if corridor == "south"
                else "Jabodetabek"
            )
        elif corridor == "tasik":
            direction = "Tasik / Cisumdawu"
        elif corridor == "west_bandung":
            direction = "Bandung (Padaleunyi)"
        else:
            direction = "Padalarang (Cipularang)"
        return (
            f"Skema «{req.get('label', requested_key)}» disesuaikan menjadi "
            f"«{eff.get('label', effective)}» karena tujuan arah {direction}."
        )
    return (
        f"Skema «{req.get('label', requested_key)}» disesuaikan menjadi "
        f"«{eff.get('label', effective)}» karena tujuan arah "
        f"{'timur (Japek)' if corridor == 'east' else 'selatan (Bogor)'}."
    )
