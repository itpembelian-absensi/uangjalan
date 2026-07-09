from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RouteFeeMaster, VehicleType
from app.money_utils import ROUTE_FEE_CATEGORY_LABELS, match_route_fee_category


@dataclass(frozen=True)
class RouteFeeDef:
    key: str
    label: str
    menu_id: str
    path: str
    permission: str
    sort_order: int
    defaults: dict[str, float]
    seed_rows: tuple[tuple[str, float], ...]


ROUTE_FEE_DEFS: tuple[RouteFeeDef, ...] = (
    RouteFeeDef(
        key="pjr",
        label="PJR",
        menu_id="master_pjr",
        path="/master-pjr",
        permission="route_fee_pjr",
        sort_order=41,
        defaults={
            "grandmax": 30000.0,
            "engkle": 30000.0,
            "double": 30000.0,
            "fuso": 60000.0,
            "tronton": 60000.0,
        },
        seed_rows=(
            ("Grand Max", 30000),
            ("Engkle", 30000),
            ("Double", 30000),
            ("Fuso", 60000),
            ("Tronton", 60000),
        ),
    ),
    RouteFeeDef(
        key="forklift_bongkaran",
        label="Forklift Bongkaran",
        menu_id="master_forklift_bongkaran",
        path="/master-forklift-bongkaran",
        permission="route_fee_forklift",
        sort_order=42,
        defaults={
            "grandmax": 10000.0,
            "engkle": 10000.0,
            "double": 30000.0,
            "fuso": 30000.0,
            "tronton": 30000.0,
        },
        seed_rows=(
            ("Grand Max", 10000),
            ("Engkle", 10000),
            ("Double", 30000),
            ("Fuso", 30000),
            ("Tronton", 30000),
        ),
    ),
    RouteFeeDef(
        key="parkir_liar",
        label="Parkir Liar",
        menu_id="master_parkir_liar",
        path="/master-parkir-liar",
        permission="route_fee_parkir_liar",
        sort_order=43,
        defaults={
            "grandmax": 5000.0,
            "engkle": 5000.0,
            "double": 5000.0,
            "fuso": 10000.0,
            "tronton": 10000.0,
        },
        seed_rows=(
            ("Grand Max", 5000),
            ("Engkle", 5000),
            ("Double", 5000),
            ("Fuso", 10000),
            ("Tronton", 10000),
        ),
    ),
    RouteFeeDef(
        key="parkir_kawasan",
        label="Parkir Kawasan",
        menu_id="master_parkir_kawasan",
        path="/master-parkir-kawasan",
        permission="route_fee_parkir_kawasan",
        sort_order=44,
        defaults={
            "grandmax": 10000.0,
            "engkle": 10000.0,
            "double": 10000.0,
            "fuso": 20000.0,
            "tronton": 20000.0,
        },
        seed_rows=(
            ("Grand Max", 10000),
            ("Engkle", 10000),
            ("Double", 10000),
            ("Fuso", 20000),
            ("Tronton", 20000),
        ),
    ),
)

ROUTE_FEE_DEF_BY_KEY = {d.key: d for d in ROUTE_FEE_DEFS}
ROUTE_FEE_KEYS = tuple(d.key for d in ROUTE_FEE_DEFS)


def get_route_fee_def(fee_type: str) -> RouteFeeDef:
    fee = ROUTE_FEE_DEF_BY_KEY.get(fee_type)
    if not fee:
        raise ValueError(f"Jenis biaya rute tidak dikenal: {fee_type}")
    return fee


def route_fee_amount_for_vehicle_type(db: Session, fee_type: str, vehicle_type_id: int | None) -> float:
    if not vehicle_type_id:
        return 0.0
    fee_def = get_route_fee_def(fee_type)
    vt = db.get(VehicleType, vehicle_type_id)
    if not vt:
        return 0.0
    category = match_route_fee_category(vt.name)
    if not category:
        return 0.0
    master_name = ROUTE_FEE_CATEGORY_LABELS[category]
    master = db.scalar(
        select(RouteFeeMaster).where(
            RouteFeeMaster.fee_type == fee_type,
            RouteFeeMaster.name == master_name,
        )
    )
    if master:
        return float(master.amount or 0)
    return float(fee_def.defaults.get(category, 0))


def apply_route_fee_field(
    db: Session,
    obj,
    fee_type: str,
    *,
    include: bool,
    vehicle_type_id: int | None,
) -> None:
    include_attr = f"include_{fee_type}"
    amount_attr = fee_type
    if include and vehicle_type_id:
        amount = route_fee_amount_for_vehicle_type(db, fee_type, vehicle_type_id)
        setattr(obj, include_attr, True)
        setattr(obj, amount_attr, amount)
    else:
        setattr(obj, include_attr, False)
        setattr(obj, amount_attr, 0.0)


def apply_route_fees_from_payload(db: Session, obj, vehicle_type_id: int | None, payload) -> None:
    from app.pelabuhan_service import apply_uang_pelabuhan_fields

    apply_uang_pelabuhan_fields(
        db,
        obj,
        include=bool(getattr(payload, "include_uang_pelabuhan", False)),
        vehicle_type_id=vehicle_type_id,
    )
    for fee_type in ROUTE_FEE_KEYS:
        apply_route_fee_field(
            db,
            obj,
            fee_type,
            include=bool(getattr(payload, f"include_{fee_type}", False)),
            vehicle_type_id=vehicle_type_id,
        )


def sum_route_fees(obj) -> float:
    total = float(obj.uang_pelabuhan or 0) if getattr(obj, "include_uang_pelabuhan", False) else 0.0
    for fee_type in ROUTE_FEE_KEYS:
        if getattr(obj, f"include_{fee_type}", False):
            total += float(getattr(obj, fee_type, 0) or 0)
    return total
