"""Probe OSM toll booth names/coords for matching with master gerbang."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
from app.toll_gate_service import _normalize_gate_name

query = """
[out:json][timeout:120];
(
  node["barrier"="toll_booth"](-6.85,106.35,-5.95,107.55);
  node["highway"="toll_gantry"](-6.85,106.35,-5.95,107.55);
);
out body;
"""
req = urllib.request.Request(
    "https://overpass-api.de/api/interpreter",
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
    rows.append((name, el["lat"], el["lon"], _normalize_gate_name(name)))

rows.sort(key=lambda r: r[0].lower())
print("count", len(rows))
for name, lat, lon, norm in rows:
    print(f"{name:45} {lat:.6f} {lon:.6f}  [{norm}]")
