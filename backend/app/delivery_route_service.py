from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    CustomerVehicleTariff,
    DeliveryRoute,
    DeliveryRouteStop,
    DeliveryRouteStopLine,
    Sale,
    SaleDetail,
    Vehicle,
)
from app.sale_lock import MSG_ROUTE_FINANCE_PAID, sale_finance_locked
from app.schemas import DeliveryRouteStopItem


def _tariff_amount(row: CustomerVehicleTariff) -> float:
    component = (
        float(row.bbm)
        + float(row.tol)
        + float(row.uang_mel or 0)
        + float(row.parkir)
        + float(row.lain_lain)
    )
    if component > 0:
        return component
    return float(row.uang_jalan)


def resolve_vehicle_type_id(db: Session, route: DeliveryRoute) -> int:
    if route.vehicle_type_id:
        return route.vehicle_type_id
    if route.vehicle_id:
        vehicle = db.get(Vehicle, route.vehicle_id)
        if vehicle and vehicle.type_id:
            return vehicle.type_id
    raise HTTPException(status_code=400, detail="Jenis kendaraan rute tidak valid.")


def tariff_amount_for_customer(db: Session, customer_id: int, vehicle_type_id: int) -> float:
    row = db.scalar(
        select(CustomerVehicleTariff).where(
            CustomerVehicleTariff.customer_id == customer_id,
            CustomerVehicleTariff.vehicle_type_id == vehicle_type_id,
        )
    )
    if not row:
        return 0.0
    return _tariff_amount(row)


def build_sale_details_from_route(db: Session, route: DeliveryRoute) -> list[dict]:
    vehicle_type_id = resolve_vehicle_type_id(db, route)
    stops = sorted(route.stops, key=lambda s: s.sort_order)
    if not stops:
        raise HTTPException(status_code=400, detail="Rute belum memiliki titik pengiriman.")
    details: list[dict] = []
    for stop in stops:
        details.append(
            {
                "customer_id": stop.customer_id,
                "vehicle_type_id": vehicle_type_id,
                "amount": tariff_amount_for_customer(db, stop.customer_id, vehicle_type_id),
            }
        )
    return details


def sync_sale_from_route(db: Session, route: DeliveryRoute) -> Sale:
    details_data = build_sale_details_from_route(db, route)
    existing = db.scalar(select(Sale).where(Sale.delivery_route_id == route.id))

    if existing and sale_finance_locked(existing):
        raise HTTPException(status_code=400, detail=MSG_ROUTE_FINANCE_PAID)

    if existing:
        sale = existing
        sale.date = route.date
        if route.driver_id is not None:
            sale.driver_id = route.driver_id
        sale.remarks = route.remarks
        db.execute(delete(SaleDetail).where(SaleDetail.sale_id == sale.id))
    else:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        sale = Sale(
            sale_no=f"SL-{timestamp}",
            date=route.date,
            vehicle_id=None,
            driver_id=route.driver_id,
            delivery_route_id=route.id,
            remarks=route.remarks,
            extra_uang_jalan=0,
        )
        db.add(sale)
        db.flush()

    for item in details_data:
        db.add(
            SaleDetail(
                sale_id=sale.id,
                customer_id=item["customer_id"],
                vehicle_type_id=item["vehicle_type_id"],
                amount=item["amount"],
            )
        )
    return sale


def _normalize_stop_lines(stop: DeliveryRouteStopItem) -> list[tuple[str, float]]:
    lines: list[tuple[str, float]] = []
    for line in stop.items or []:
        name = (line.item_name or "").strip()
        if not name:
            continue
        qty = float(line.quantity)
        if qty <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Quantity barang '{name}' harus lebih dari 0.",
            )
        lines.append((name, qty))
    return lines


def replace_route_stops(db: Session, route: DeliveryRoute, stops: list[DeliveryRouteStopItem]) -> None:
    db.execute(delete(DeliveryRouteStop).where(DeliveryRouteStop.route_id == route.id))
    seen: set[int] = set()
    for idx, stop_item in enumerate(stops):
        customer_id = stop_item.customer_id
        if customer_id in seen:
            raise HTTPException(status_code=400, detail="Customer duplikat pada rute")
        seen.add(customer_id)
        if not db.get(Customer, customer_id):
            raise HTTPException(status_code=400, detail=f"Customer {customer_id} tidak ditemukan")

        lines = _normalize_stop_lines(stop_item)
        if not lines:
            raise HTTPException(
                status_code=400,
                detail="Setiap customer pada rute wajib memiliki minimal 1 barang dengan quantity.",
            )

        stop = DeliveryRouteStop(
            route_id=route.id,
            customer_id=customer_id,
            sort_order=idx,
            description=(stop_item.description or None),
            entity_code=(stop_item.entity_code or None),
        )
        db.add(stop)
        db.flush()

        for line_idx, (item_name, quantity) in enumerate(lines):
            db.add(
                DeliveryRouteStopLine(
                    stop_id=stop.id,
                    item_name=item_name,
                    quantity=quantity,
                    sort_order=line_idx,
                )
            )


def _format_quantity(qty: float) -> str:
    return str(int(qty)) if qty == int(qty) else str(qty)


def stop_items_lines(stop: DeliveryRouteStop) -> list[dict]:
    return [
        {"item_name": line.item_name, "quantity": float(line.quantity)}
        for line in sorted(stop.lines, key=lambda x: x.sort_order)
    ]


def stop_items_qty_total(stop: DeliveryRouteStop) -> float:
    return sum(item["quantity"] for item in stop_items_lines(stop))


def format_stop_items_summary(stop: DeliveryRouteStop) -> str:
    parts = []
    for item in stop_items_lines(stop):
        parts.append(f"{item['item_name']} x {_format_quantity(item['quantity'])}")
    return "; ".join(parts)
