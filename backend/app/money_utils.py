from __future__ import annotations

import math

PELABUHAN_VEHICLE_ORDER = ("grandmax", "tronton", "fuso", "double", "engkle", "engkel")
ROUTE_FEE_VEHICLE_ORDER = ("grandmax", "tronton", "fuso", "double", "engkle", "engkel", "viar")
ROUTE_FEE_CATEGORY_LABELS = {
    "grandmax": "Grand Max",
    "engkle": "Engkle",
    "double": "Double",
    "fuso": "Fuso",
    "tronton": "Tronton",
    "viar": "Viar",
}
PELABUHAN_MASTER_LABELS = {
    "grandmax": "Grand Max",
    "engkle": "Engkle",
    "double": "Double",
    "fuso": "Fuso",
    "tronton": "Tronton",
}
PELABUHAN_DEFAULT_AMOUNTS = {
    "grandmax": 30000.0,
    "engkle": 30000.0,
    "double": 30000.0,
    "fuso": 33000.0,
    "tronton": 33000.0,
}


def normalize_vehicle_type_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "")


def match_pelabuhan_category(vehicle_type_name: str) -> str | None:
    normalized = normalize_vehicle_type_name(vehicle_type_name)
    for key in PELABUHAN_VEHICLE_ORDER:
        if key in normalized:
            return "engkle" if key == "engkel" else key
    return None


def match_route_fee_category(vehicle_type_name: str) -> str | None:
    normalized = normalize_vehicle_type_name(vehicle_type_name)
    for key in ROUTE_FEE_VEHICLE_ORDER:
        if key in normalized:
            return "engkle" if key == "engkel" else key
    return None


def compute_uang_jalan_totals(
    base_amount: float, extra_amount: float = 0, route_fees_amount: float = 0
) -> dict[str, float]:
    """Pembulatan total ke atas ke ribuan terdekat (sama dengan frontend)."""
    subtotal = float(base_amount or 0) + float(extra_amount or 0) + float(route_fees_amount or 0)
    if subtotal <= 0:
        return {"subtotal": 0.0, "rounding": 0.0, "total": 0.0}
    total = math.ceil(subtotal / 1000) * 1000
    return {"subtotal": subtotal, "rounding": total - subtotal, "total": float(total)}
