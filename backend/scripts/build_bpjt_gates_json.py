"""
Bangun bpjt_jabodetabek_gates.json dari tabel tarif BPJT (format baris markdown).
Jalankan: python scripts/build_bpjt_gates_json.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bpjt_jabodetabek_gates.json"

RAW_LINES = """
| 1 | Jabodetabek | Jakarta-Bogor-Ciawi | Jakarta | Ciawi | Rp7,500 | Rp12,000 | Rp17,000 | Terbuka |
| 2 | Jabodetabek | Prof.Dr.Ir.Soedijatmo | Prof.Dr.Ir.Soedijatmo | Prof.Dr.Ir.Soedijatmo | Rp8,500 | Rp11,000 | Rp12,000 | Terbuka |
| 3 | Jabodetabek | Cawang-Tomang-Pluit (CTC) | Cawang | Pluit | Rp11,000 | Rp16,500 | Rp19,000 | Terbuka |
| 4 | Jabodetabek | Cawang-Tj. Priok-Ancol Timur-Jembatan Tiga/Pluit | Cawang | Jembatan Tiga/Pluit | Rp11,000 | Rp16,500 | Rp19,000 |
| 5 | Jabodetabek | JORR S | Pondok Pinang | Taman Mini | Rp17,000 | Rp25,000 | Rp33,500 | Terbuka |
| 6 | Jabodetabek | JORR NON S | Rorotan | Kebon Bawang | Rp17,000 | Rp25,000 | Rp33,500 |
| 7 | Jabodetabek | JORR W1 (Kebon Jeruk-Penjaringan) | Kebon Jeruk | Penjaringan | Rp17,000 | Rp25,000 | Rp33,500 |
| 8 | Jabodetabek | JORR W2 Utara (Kebon Jeruk-Ulujami) | Kebon Jeruk | Ulujami | Rp17,000 | Rp25,000 | Rp33,500 |
| 9 | Jabodetabek | Akses Tanjung Priuk | Akses Tanjung Priuk | Seksi E1,E2,E2A | Rp17,000 | Rp25,000 | Rp33,500 |
| 10 | Jabodetabek | Bogor Ring Road Seksi I-IIIA (Sentul Selatan-Simpang Semplak) | Sentul Selatan | Simpang Semplak | Rp15,000 | Rp22,500 | Rp30,000 |
| 11 | Jabodetabek | Cinere-Jagorawi | SS Cimanggis | Cinere | Rp15,000 | Rp23,000 | Rp30,500 |
| 12 | Jabodetabek | Pondok Aren-Bintaro Viaduct-Ulujami | Pondok Aren | Ulujami | Rp17,000 | Rp25,000 | Rp33,500 |
| 13 | Jabodetabek | Pondok Aren-Serpong | Pondok Aren | Serpong | Rp9,500 | Rp14,000 | Rp18,500 | Terbuka |
| 14 | Jabodetabek | Bekasi-Cawang-Kampung Melayu | Casablanca | GT Jatiwaringin 1 dan 2 | Rp10,500 | Rp15,500 | Rp20,500 | Terbuka |
| Casablanca | GT Pondok Kelapa 1 dan 2 | Rp16,000 | Rp23,500 | Rp31,500 |
| Casablanca | GT Bintara Jaya dan Jakasampurna | Rp22,500 | Rp33,500 | Rp44,500 |
| Casablanca | GT Marga Jaya 1 dan 2 | Rp28,500 | Rp43,000 | Rp57,000 |
| 15 | Jabodetabek | Depok-Antasari | Antasari-Brigif-Sawangan | Antasari-Brigif-Sawangan | Rp8,000 | Rp12,000 | Rp16,000 | Terbuka |
| 16 | Jabodetabek | Kunciran-Serpong | JC Kunciran | SS Parigi | Rp12,500 | Rp19,000 | Rp25,000 | Terbuka |
| JC Kunciran | JC Serpong | Rp21,000 | Rp31,500 | Rp41,500 |
| SS Parigi | JC Kunciran | Rp12,500 | Rp19,000 | Rp25,000 |
| SS Parigi | JC Serpong | Rp21,000 | Rp31,500 | Rp41,500 |
| JC Serpong | JC Kunciran | Rp8,500 | Rp12,500 | Rp16,500 |
| JC Serpong | SS Parigi | Rp8,500 | Rp12,500 | Rp16,500 |
| 17 | Jabodetabek | Cimanggis-Cibitung Seksi 1-2A | Junction Cimanggis | On/Off Ramp Jatikarya | Rp5,500 | Rp8,500 | Rp11,500 | Terbuka |
| Junction Cimanggis | Simpang Susun Cikeas | Rp13,500 | Rp20,000 | Rp27,000 | Tertutup |
| On/Off Ramp Jatikarya | Junction Cimanggis | Rp5,500 | Rp8,500 | Rp11,500 | Terbuka |
| Simpang Susun Cikeas | Junction Cimanggis | Rp13,500 | Rp20,000 | Rp27,000 | Tertutup |
| 17 | Jabodetabek | Cimanggis-Cibitung Seksi 2B | Jatikarya | SS Cikeas | Rp8,000 | Rp11,500 | Rp15,500 | Tertutup |
| Jatikarya | SS Narogong | Rp14,000 | Rp21,000 | Rp28,500 |
| Jatikarya | SS Setu Selatan | Rp27,500 | Rp41,000 | Rp54,500 |
| Jatikarya | SS Setu Utara | Rp43,500 | Rp65,500 | Rp87,000 |
| Jatikarya | JC Cibitung | Rp48,500 | Rp72,500 | Rp97,000 |
| SS Cikeas | SS Narogong | Rp6,500 | Rp9,500 | Rp12,500 |
| SS Cikeas | SS Setu Selatan | Rp19,500 | Rp29,000 | Rp39,000 |
| SS Cikeas | SS Setu Utara | Rp35,500 | Rp53,500 | Rp71,500 |
| SS Cikeas | JC Cibitung | Rp40,500 | Rp61,000 | Rp81,000 |
| SS Cikeas | Jatikarya | Rp8,000 | Rp11,500 | Rp15,500 |
| SS Narogong | SS Setu Selatan | Rp13,000 | Rp19,500 | Rp26,500 |
| SS Narogong | SS Setu Utara | Rp29,500 | Rp44,000 | Rp58,500 |
| SS Narogong | JC Cibitung | Rp34,000 | Rp51,500 | Rp68,500 |
| SS Narogong | Jatikarya | Rp14,000 | Rp21,000 | Rp28,500 |
| SS Narogong | SS Cikeas | Rp6,500 | Rp9,500 | Rp12,500 |
| SS Setu Selatan | SS Setu Utara | Rp16,000 | Rp24,500 | Rp32,500 |
| SS Setu Selatan | JC Cibitung | Rp21,000 | Rp31,500 | Rp42,000 |
| SS Setu Selatan | Jatikarya | Rp27,500 | Rp41,000 | Rp54,500 |
| SS Setu Selatan | SS Cikeas | Rp19,500 | Rp29,000 | Rp39,000 |
| SS Setu Selatan | SS Narogong | Rp13,000 | Rp19,500 | Rp26,500 |
| SS Setu Utara | JC Cibitung | Rp5,000 | Rp7,500 | Rp10,000 |
| SS Setu Utara | Jatikarya | Rp43,500 | Rp65,500 | Rp87,000 |
| SS Setu Utara | SS Cikeas | Rp35,500 | Rp53,500 | Rp71,500 |
| SS Setu Utara | SS Narogong | Rp29,500 | Rp44,000 | Rp58,500 |
| SS Setu Utara | SS Setu Selatan | Rp16,000 | Rp24,500 | Rp32,500 |
| JC Cibitung | Jatikarya | Rp48,500 | Rp72,500 | Rp97,000 |
| JC Cibitung | SS Cikeas | Rp40,500 | Rp61,000 | Rp81,000 |
| JC Cibitung | SS Narogong | Rp34,000 | Rp51,500 | Rp68,500 |
| JC Cibitung | SS Setu Selatan | Rp21,000 | Rp31,500 | Rp42,000 |
| JC Cibitung | SS Setu Utara | Rp5,000 | Rp7,500 | Rp10,000 |
| 18 | Jabodetabek | Serpong-Cinere | Junction Serpong | Pamulang | Rp12,000 | Rp18,000 | Rp24,000 | Tertutup |
| Junction Serpong | Cinere | Rp18,500 | Rp28,000 | Rp37,000 |
| Pamulang | Junction Serpong | Rp12,000 | Rp18,000 | Rp24,000 |
| Pamulang | Cinere | Rp6,500 | Rp10,000 | Rp13,500 |
| Cinere | Pamulang | Rp6,500 | Rp10,000 | Rp13,500 |
| Cinere | Junction Serpong | Rp18,500 | Rp28,000 | Rp37,000 |
| 19 | Jabodetabek | Cengkareng-Batu Ceper-Kunciran | JC Benda | Tanah Tinggi | Rp15,500 | Rp23,000 | Rp30,500 | Tertutup |
| JC Benda | Pinang | Rp23,500 | Rp35,500 | Rp47,000 |
| JC Benda | JC Kunciran | Rp27,000 | Rp41,000 | Rp54,500 |
| Benda Utama | Tanah Tinggi | Rp10,500 | Rp16,000 | Rp21,000 |
| Benda Utama | Pinang | Rp19,000 | Rp28,000 | Rp37,500 |
| Benda Utama | JC Kunciran | Rp22,500 | Rp33,500 | Rp45,000 |
| Tanah Tinggi | JC Benda | Rp15,500 | Rp23,000 | Rp30,500 |
| Tanah Tinggi | Benda Utama | Rp10,500 | Rp16,000 | Rp21,000 |
| Buaran Indah | Pinang | Rp5,000 | Rp8,000 | Rp10,500 |
| Buaran Indah | JC Kunciran | Rp9,000 | Rp13,000 | Rp17,500 |
| Pinang | JC Kunciran | Rp3,000 | Rp4,500 | Rp5,500 |
| Pinang | JC Benda | Rp23,500 | Rp35,500 | Rp47,000 |
| Pinang | Benda Utama | Rp19,000 | Rp28,000 | Rp37,500 |
| Pinang | Buaran Indah | Rp5,000 | Rp8,000 | Rp10,500 |
| JC Kunciran | JC Benda | Rp27,000 | Rp41,000 | Rp54,500 |
| JC Kunciran | Benda Utama | Rp22,500 | Rp33,500 | Rp45,000 |
| JC Kunciran | Buaran Indah | Rp9,000 | Rp13,000 | Rp17,500 |
| JC Kunciran | Pinang | Rp3,000 | Rp4,500 | Rp5,500 |
| 20 | Jabodetabek | Cibitung-Cilincing Seksi 1 | Jc Cibitung | Telaga Asih | Rp6,500 | Rp9,500 | Rp13,000 | Tertutup |
| Telaga Asih | Jc Cibitung | Rp6,500 | Rp9,500 | Rp13,000 |
| 21 | Jabodetabek | Cibitung-Cilincing Seksi 2 & 3 | Cibitung | Gabus | Rp25,500 | Rp38,000 | Rp50,500 | Tertutup |
| Cibitung | Tarumajaya | Rp54,000 | Rp81,000 | Rp107,500 |
| Telaga Asih | Gabus | Rp20,000 | Rp30,000 | Rp40,000 |
| Telaga Asih | Tarumajaya | Rp48,500 | Rp73,000 | Rp97,000 |
| Gabus | Telaga Asih | Rp20,000 | Rp30,000 | Rp40,000 |
| Gabus | Cibitung | Rp25,500 | Rp38,000 | Rp50,500 |
| Gabus | Tarumajaya | Rp28,500 | Rp43,000 | Rp57,000 |
| Tarumajaya | Gabus | Rp28,500 | Rp43,000 | Rp57,000 |
| Tarumajaya | Telaga Asih | Rp48,500 | Rp73,000 | Rp97,000 |
| Tarumajaya | Cibitung | Rp54,000 | Rp81,000 | Rp107,500 |
| 21 | Jabodetabek | Cibitung-Cilincing Seksi 4 | Cibitung | Cilincing | Rp68,500 | Rp102,500 | Rp136,500 | Tertutup |
| Telaga Asih | Cilincing | Rp63,000 | Rp94,500 | Rp126,000 |
| Gabus | Cilincing | Rp43,000 | Rp64,500 | Rp86,000 |
| Tarumajaya | Cilincing | Rp14,500 | Rp21,500 | Rp29,000 |
| Cilincing | Tarumajaya | Rp14,500 | Rp21,500 | Rp29,000 |
| Cilincing | Gabus | Rp43,000 | Rp64,500 | Rp86,000 |
| Cilincing | Telaga Asih | Rp63,000 | Rp94,500 | Rp126,000 |
| Cilincing | Cibitung | Rp68,500 | Rp102,500 | Rp136,500 |
| 22 | Jabodetabek | 6 (Enam) Ruas Dalam Kota Jakarta Seksi A (Kelapa Gading-Pulo Gebang) | Kelapa Gading | Pulogebang | Rp22,000 | Rp33,000 | Rp44,000 | Terbuka |
| 23 | Jabodetabek | Serpong-Balaraja Seksi 1 (Serpong-SS Legok) | Serpong | SS CBD | Rp6,000 | Rp9,000 | Rp12,500 | Semi Tertutup |
| SS CBD | SS Legok | Rp7,000 | Rp11,000 | Rp14,500 |
"""


def _parse_rp(value: str) -> int:
    cleaned = value.strip().lower().replace("rp", "").replace(".", "").replace(",", "").strip()
    if not cleaned:
        return 0
    num = float(cleaned)
    if num < 1000:
        num *= 1000
    return int(round(num))


def _split_cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _rates_from_cells(cells: list[str]) -> dict[str, int] | None:
    money = [c for c in cells if c.lower().startswith("rp")]
    if len(money) < 3:
        return None
    gol1 = _parse_rp(money[0])
    gol23 = _parse_rp(money[1])
    gol45 = _parse_rp(money[2])
    return {"I": gol1, "II": gol23, "III": gol23, "IV": gol45, "V": gol45}


def _normalize_gate(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def parse_matrices() -> list[dict]:
    current_section: str | None = None
    matrices: dict[str, dict] = {}

    for raw in RAW_LINES.strip().splitlines():
        raw = raw.strip()
        if not raw.startswith("|"):
            continue
        cells = _split_cells(raw)
        if not cells:
            continue

        if cells[0].isdigit() and len(cells) >= 8 and cells[1].lower() == "jabodetabek":
            current_section = cells[2].strip()
            entry = _normalize_gate(cells[3])
            exit_gate = _normalize_gate(cells[4])
            rates = _rates_from_cells(cells[5:])
            if rates and entry and exit_gate and entry != exit_gate:
                bucket = matrices.setdefault(current_section, {"section_name": current_section, "fares": []})
                bucket["fares"].append({"entry": entry, "exit": exit_gate, "rates": rates})
            continue

        if not current_section:
            continue

        rates = _rates_from_cells(cells)
        if not rates:
            continue

        non_money = [c for c in cells if not c.lower().startswith("rp") and c.lower() not in ("terbuka", "tertutup", "semi tertutup")]
        if len(non_money) >= 2:
            entry = _normalize_gate(non_money[0])
            exit_gate = _normalize_gate(non_money[1])
        elif len(non_money) == 1:
            continue
        else:
            continue

        if entry and exit_gate and entry != exit_gate:
            bucket = matrices.setdefault(current_section, {"section_name": current_section, "fares": []})
            bucket["fares"].append({"entry": entry, "exit": exit_gate, "rates": rates})

    result = []
    for section_name, data in matrices.items():
        seen = set()
        fares = []
        for fare in data["fares"]:
            key = (fare["entry"].lower(), fare["exit"].lower())
            if key in seen:
                continue
            seen.add(key)
            fares.append(fare)
        result.append({"section_name": section_name, "fares": fares})
    return result


def main() -> None:
    matrices = parse_matrices()
    payload = {
        "source": "BPJT Tarif Tol Jabodetabek",
        "source_url": "https://bpjt.pu.go.id/info-tarif-dan-golongan/",
        "matrices": matrices,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total_fares = sum(len(m["fares"]) for m in matrices)
    print(f"Wrote {len(matrices)} sections, {total_fares} fare pairs -> {OUT}")


if __name__ == "__main__":
    main()
