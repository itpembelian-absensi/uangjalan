from __future__ import annotations

import math


def compute_uang_jalan_totals(base_amount: float, extra_amount: float = 0) -> dict[str, float]:
    """Pembulatan total ke atas ke ribuan terdekat (sama dengan frontend)."""
    subtotal = float(base_amount or 0) + float(extra_amount or 0)
    if subtotal <= 0:
        return {"subtotal": 0.0, "rounding": 0.0, "total": 0.0}
    total = math.ceil(subtotal / 1000) * 1000
    return {"subtotal": subtotal, "rounding": total - subtotal, "total": float(total)}
