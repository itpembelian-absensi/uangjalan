from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.money_utils import PELABUHAN_DEFAULT_AMOUNTS, PELABUHAN_MASTER_LABELS, match_pelabuhan_category
from app.models import UangPelabuhanMaster, VehicleType


def resolve_uang_pelabuhan(db: Session, vt: VehicleType) -> tuple[str | None, float]:
    if vt.uang_pelabuhan:
        return vt.uang_pelabuhan.name, float(vt.uang_pelabuhan.amount or 0)
    category = match_pelabuhan_category(vt.name)
    if not category:
        return None, 0.0
    master_name = PELABUHAN_MASTER_LABELS[category]
    master = db.scalar(
        select(UangPelabuhanMaster).where(UangPelabuhanMaster.name == master_name)
    )
    if master:
        return master.name, float(master.amount or 0)
    return master_name, float(PELABUHAN_DEFAULT_AMOUNTS.get(category, 0))


def uang_pelabuhan_amount_for_vehicle_type(db: Session, vehicle_type_id: int | None) -> float:
    if not vehicle_type_id:
        return 0.0
    vt = db.scalar(
        select(VehicleType)
        .options(selectinload(VehicleType.uang_pelabuhan))
        .where(VehicleType.id == vehicle_type_id)
    )
    if not vt:
        return 0.0
    _, amount = resolve_uang_pelabuhan(db, vt)
    return amount


def apply_uang_pelabuhan_fields(
    db: Session,
    obj,
    *,
    include: bool,
    vehicle_type_id: int | None,
) -> None:
    if include and vehicle_type_id:
        amount = uang_pelabuhan_amount_for_vehicle_type(db, vehicle_type_id)
        obj.include_uang_pelabuhan = True
        obj.uang_pelabuhan = amount
    else:
        obj.include_uang_pelabuhan = False
        obj.uang_pelabuhan = 0.0
