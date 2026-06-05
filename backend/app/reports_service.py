from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.delivery_route_service import (
    format_stop_items_summary,
    stop_items_lines,
    stop_items_qty_total,
)
from app.models import (
    CashDisbursement,
    Customer,
    DeliveryRoute,
    DeliveryRouteStop,
    Sale,
    VehicleType,
)


def _disbursed_date_filters(from_date: date | None, to_date: date | None):
    clauses = []
    if from_date:
        start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        clauses.append(CashDisbursement.disbursed_at >= start)
    if to_date:
        end = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        clauses.append(CashDisbursement.disbursed_at <= end)
    return clauses


def driver_summary(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    return []


def customer_summary(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    amount_sum = func.coalesce(func.sum(CashDisbursement.amount), 0).label("total_amount")
    stmt = (
        select(
            Customer.id,
            Customer.name,
            func.count(CashDisbursement.id).label("transaction_count"),
            amount_sum,
        )
        .select_from(Customer)
        .outerjoin(CashDisbursement, CashDisbursement.customer_id == Customer.id)
        .where(*_disbursed_date_filters(from_date, to_date))
        .group_by(Customer.id, Customer.name)
        .having(func.count(CashDisbursement.id) > 0)
        .order_by(Customer.name.asc())
    )
    rows = db.execute(stmt).all()
    return [
        {
            "customer_id": r.id,
            "customer_name": r.name,
            "delivery_count": int(r.transaction_count),
            "total_amount": float(r.total_amount),
        }
        for r in rows
    ]


def disbursement_detail(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    driver_id: int | None = None,
    customer_id: int | None = None,
) -> list[dict]:
    del driver_id
    stmt = (
        select(
            CashDisbursement.id,
            CashDisbursement.disbursed_at,
            Customer.name.label("customer_name"),
            VehicleType.name.label("vehicle_type_name"),
            CashDisbursement.amount,
            CashDisbursement.description,
        )
        .join(Customer, Customer.id == CashDisbursement.customer_id)
        .outerjoin(VehicleType, VehicleType.id == CashDisbursement.vehicle_type_id)
        .where(*_disbursed_date_filters(from_date, to_date))
        .order_by(CashDisbursement.disbursed_at.desc())
    )
    if customer_id:
        stmt = stmt.where(CashDisbursement.customer_id == customer_id)

    rows = db.execute(stmt).all()
    return [
        {
            "id": r.id,
            "disbursed_at": r.disbursed_at,
            "customer_name": r.customer_name,
            "vehicle_type_name": r.vehicle_type_name or "-",
            "amount": float(r.amount),
            "description": r.description,
        }
        for r in rows
    ]


def grand_total(rows: list[dict]) -> float:
    return sum(r.get("amount", r.get("total_amount", 0)) for r in rows)


def delivery_route_report(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_type_id: int | None = None,
    vehicle_id: int | None = None,
) -> dict:
    stmt = (
        select(DeliveryRoute)
        .options(
            selectinload(DeliveryRoute.stops).selectinload(DeliveryRouteStop.lines),
        )
        .order_by(DeliveryRoute.date.desc(), DeliveryRoute.created_at.desc())
    )
    if from_date:
        stmt = stmt.where(DeliveryRoute.date >= from_date)
    if to_date:
        stmt = stmt.where(DeliveryRoute.date <= to_date)
    if vehicle_type_id:
        stmt = stmt.where(DeliveryRoute.vehicle_type_id == vehicle_type_id)
    elif vehicle_id:
        stmt = stmt.where(DeliveryRoute.vehicle_id == vehicle_id)

    routes = db.scalars(stmt).all()
    route_rows: list[dict] = []
    stop_rows: list[dict] = []
    total_stops = 0
    total_items_qty = 0.0

    for route in routes:
        vehicle_type = db.get(VehicleType, route.vehicle_type_id)
        sale = db.scalar(select(Sale).where(Sale.delivery_route_id == route.id))
        type_name = vehicle_type.name if vehicle_type else "-"
        sale_no = sale.sale_no if sale else None

        sorted_stops = sorted(route.stops, key=lambda s: s.sort_order)
        customer_names: list[str] = []
        for idx, stop in enumerate(sorted_stops, start=1):
            cust = db.get(Customer, stop.customer_id)
            name = cust.name if cust else "-"
            customer_names.append(name)
            items = stop_items_lines(stop)
            qty_total = stop_items_qty_total(stop)
            total_items_qty += qty_total
            stop_rows.append(
                {
                    "route_no": route.route_no,
                    "route_date": route.date.isoformat(),
                    "vehicle_type_name": type_name,
                    "stop_order": idx,
                    "customer_name": name,
                    "description": stop.description,
                    "entity_code": stop.entity_code,
                    "ritase": route.ritpiase,
                    "items": items,
                    "items_qty_total": qty_total,
                    "items_count": len(items),
                    "items_summary": format_stop_items_summary(stop) or None,
                    "remarks": route.remarks,
                    "sale_no": sale_no,
                }
            )

        stop_count = len(sorted_stops)
        total_stops += stop_count
        customers_str = "; ".join(f"{i}. {n}" for i, n in enumerate(customer_names, start=1))
        route_rows.append(
            {
                "id": route.id,
                "route_no": route.route_no,
                "date": route.date.isoformat(),
                "vehicle_type_name": type_name,
                "stop_count": stop_count,
                "customers": customers_str or "-",
                "ritase": route.ritpiase,
                "remarks": route.remarks,
                "sale_no": sale_no,
            }
        )

    return {
        "total_routes": len(route_rows),
        "total_stops": total_stops,
        "total_items_qty": total_items_qty,
        "routes": route_rows,
        "stop_rows": stop_rows,
    }
