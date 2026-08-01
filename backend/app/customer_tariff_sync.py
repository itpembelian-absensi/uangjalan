"""Sinkron BBM / Uang Mel master → tarif customer.

Kunci Finance membekukan ruas tol (dan transaksi sudah dibayar).
BBM & Uang Mel tetap ikut update dari master BBM / Uang Mel / jenis kendaraan.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.delivery_route_service import refresh_customer_tariff_in_sales
from app.models import (
    Customer,
    CustomerVehicleTariff,
    VehicleType,
)


def _distance_km_from_customer(customer: Customer) -> float | None:
    raw = customer.custom_toll_breakdown
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    for row in data:
        if not isinstance(row, dict) or not row.get("_route_meta"):
            continue
        km = row.get("distance_km")
        if km is None:
            continue
        try:
            value = float(km)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _calc_bbm_amount(
    distance_km: float, km_per_liter: float | None, bbm_price: float | None
) -> float | None:
    if not distance_km or not km_per_liter or float(km_per_liter) <= 0:
        return None
    liters_round_trip = (distance_km / float(km_per_liter)) * 2
    if bbm_price is None:
        return float(round(liters_round_trip))
    raw = liters_round_trip * float(bbm_price)
    return float(round(raw / 1000) * 1000)


def _recompute_uang_jalan(row: CustomerVehicleTariff) -> None:
    row.uang_jalan = (
        float(row.bbm or 0)
        + float(row.tol or 0)
        + float(row.uang_mel or 0)
        + float(row.parkir or 0)
        + float(row.lain_lain or 0)
    )


def propagate_bbm_uang_mel_to_customers(
    db: Session,
    *,
    bbm_id: int | None = None,
    uang_mel_id: int | None = None,
    vehicle_type_id: int | None = None,
) -> int:
    """
    Update kolom BBM dan/atau Uang Mel di CustomerVehicleTariff.
    Termasuk customer Finance terkunci. Kolom Tol tidak diubah.
    Sale yang sudah dibayar Finance tidak ikut (refresh_customer_tariff_in_sales).
    """
    if bbm_id is None and uang_mel_id is None and vehicle_type_id is None:
        return 0

    vt_stmt = select(VehicleType).options(
        selectinload(VehicleType.bbm),
        selectinload(VehicleType.uang_mel),
    )
    if vehicle_type_id is not None:
        vt_stmt = vt_stmt.where(VehicleType.id == vehicle_type_id)
    elif bbm_id is not None and uang_mel_id is not None:
        vt_stmt = vt_stmt.where(
            (VehicleType.bbm_id == bbm_id) | (VehicleType.uang_mel_id == uang_mel_id)
        )
    elif bbm_id is not None:
        vt_stmt = vt_stmt.where(VehicleType.bbm_id == bbm_id)
    else:
        vt_stmt = vt_stmt.where(VehicleType.uang_mel_id == uang_mel_id)

    vehicle_types = list(db.scalars(vt_stmt).all())
    if not vehicle_types:
        return 0

    vt_by_id = {vt.id: vt for vt in vehicle_types}
    type_ids = list(vt_by_id.keys())

    tariffs = list(
        db.scalars(
            select(CustomerVehicleTariff).where(
                CustomerVehicleTariff.vehicle_type_id.in_(type_ids)
            )
        ).all()
    )
    customer_ids = {t.customer_id for t in tariffs}
    customers = {
        c.id: c
        for c in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
    }

    updated_tariffs = 0
    touched_customers: set[int] = set()

    for row in tariffs:
        vt = vt_by_id.get(row.vehicle_type_id)
        if not vt:
            continue
        customer = customers.get(row.customer_id)
        changed = False

        update_mel = uang_mel_id is not None or vehicle_type_id is not None
        update_bbm = bbm_id is not None or vehicle_type_id is not None

        if update_mel:
            mel_amount = float(vt.uang_mel.amount) if vt.uang_mel else 0.0
            if float(row.uang_mel or 0) != mel_amount:
                row.uang_mel = mel_amount
                changed = True

        if update_bbm and customer is not None:
            distance_km = _distance_km_from_customer(customer)
            bbm_price = float(vt.bbm.price) if vt.bbm else None
            new_bbm = (
                _calc_bbm_amount(distance_km, vt.km_per_liter, bbm_price)
                if distance_km
                else None
            )
            if new_bbm is not None and float(row.bbm or 0) != new_bbm:
                row.bbm = new_bbm
                changed = True

        if changed:
            _recompute_uang_jalan(row)
            updated_tariffs += 1
            touched_customers.add(row.customer_id)

    for cid in touched_customers:
        refresh_customer_tariff_in_sales(db, cid)

    return updated_tariffs
