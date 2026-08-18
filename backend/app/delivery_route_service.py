from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Customer,
    CustomerVehicleTariff,
    DeliveryRoute,
    DeliveryRouteStop,
    DeliveryRouteStopLine,
    Sale,
    SaleDetail,
    Vehicle,
    VehicleType,
    WarehouseSetting,
)
from app.money_utils import calc_bbm_amount
from app.route_fee_service import apply_route_fees_from_payload
from app.routing_service import sequential_driving_km
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
    stored = float(row.uang_jalan or 0)
    # Gunakan total tersimpan jika komponen di DB belum lengkap (mis. BBM belum terisi).
    if stored > 0 and stored > component:
        return stored
    if component > 0:
        return component
    return stored


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


def _tariff_row(db: Session, customer_id: int, vehicle_type_id: int) -> CustomerVehicleTariff | None:
    return db.scalar(
        select(CustomerVehicleTariff).where(
            CustomerVehicleTariff.customer_id == customer_id,
            CustomerVehicleTariff.vehicle_type_id == vehicle_type_id,
        )
    )


def _has_map_coords(lat, lng) -> bool:
    try:
        return lat is not None and lng is not None and float(lat) != 0 and float(lng) != 0
    except (TypeError, ValueError):
        return False


def _warehouse_point(db: Session) -> tuple[float, float] | None:
    warehouse = db.scalar(select(WarehouseSetting).order_by(WarehouseSetting.id.asc()).limit(1))
    if not warehouse or not _has_map_coords(warehouse.latitude, warehouse.longitude):
        return None
    return (float(warehouse.latitude), float(warehouse.longitude))


def sequential_km_for_route(db: Session, route: DeliveryRoute) -> float | None:
    origin = _warehouse_point(db)
    if not origin:
        return None
    points: list[tuple[float, float]] = [origin]
    for stop in sorted(route.stops, key=lambda s: s.sort_order):
        customer = db.get(Customer, stop.customer_id)
        if not customer or not _has_map_coords(customer.latitude, customer.longitude):
            continue
        points.append((float(customer.latitude), float(customer.longitude)))
    if len(points) < 3:
        return None
    return sequential_driving_km(points)


def sequential_bbm_for_route(db: Session, route: DeliveryRoute) -> float | None:
    km = sequential_km_for_route(db, route)
    if not km:
        return None
    try:
        vehicle_type_id = resolve_vehicle_type_id(db, route)
    except HTTPException:
        return None
    vt = db.scalar(
        select(VehicleType)
        .options(selectinload(VehicleType.bbm))
        .where(VehicleType.id == vehicle_type_id)
    )
    if not vt:
        return None
    bbm_price = float(vt.bbm.price) if vt.bbm else None
    return calc_bbm_amount(km, vt.km_per_liter, bbm_price)


def _replace_bbm_in_amount(amount: float, tariff_bbm: float, sequential_bbm: float) -> float:
    if not (tariff_bbm > 0):
        return amount
    other = max(0.0, float(amount) - float(tariff_bbm))
    return other + float(sequential_bbm)


def apply_sequential_bbm_to_details(
    db: Session, route: DeliveryRoute, details: list[dict]
) -> list[dict]:
    if len(details) < 2:
        return details
    sequential_bbm = sequential_bbm_for_route(db, route)
    if sequential_bbm is None:
        return details
    for item in details:
        row = _tariff_row(db, item["customer_id"], item["vehicle_type_id"])
        if not row:
            continue
        tariff_bbm = float(row.bbm or 0)
        item["amount"] = _replace_bbm_in_amount(_tariff_amount(row), tariff_bbm, sequential_bbm)
    return details


def apply_sequential_bbm_to_sale(db: Session, route: DeliveryRoute, sale: Sale) -> None:
    if sale_finance_locked(sale):
        return
    details = list(sale.details or [])
    if len(details) < 2:
        return
    sequential_bbm = sequential_bbm_for_route(db, route)
    if sequential_bbm is None:
        return
    for row in details:
        tariff = _tariff_row(db, row.customer_id, row.vehicle_type_id or 0)
        if not tariff:
            continue
        tariff_bbm = float(tariff.bbm or 0)
        row.amount = _replace_bbm_in_amount(_tariff_amount(tariff), tariff_bbm, sequential_bbm)


def customers_missing_tariff(db: Session, route: DeliveryRoute) -> list[str]:
    """Nama customer yang belum punya tarif uang jalan untuk jenis kendaraan rute."""
    vehicle_type_id = resolve_vehicle_type_id(db, route)
    missing: list[str] = []
    seen: set[int] = set()
    for stop in sorted(route.stops, key=lambda s: s.sort_order):
        if stop.customer_id in seen:
            continue
        seen.add(stop.customer_id)
        if tariff_amount_for_customer(db, stop.customer_id, vehicle_type_id) <= 0:
            cust = db.get(Customer, stop.customer_id)
            missing.append(cust.name if cust else f"Customer #{stop.customer_id}")
    return missing


def assert_route_tariffs_complete(db: Session, route: DeliveryRoute) -> None:
    missing = customers_missing_tariff(db, route)
    if not missing:
        return
    vehicle_type = db.get(VehicleType, resolve_vehicle_type_id(db, route))
    vt_name = vehicle_type.name if vehicle_type else "jenis kendaraan rute"
    names = ", ".join(missing)
    raise HTTPException(
        status_code=400,
        detail=(
            f"Lengkapi master customer terlebih dahulu. "
            f"Tarif uang jalan ({vt_name}) belum diisi untuk: {names}."
        ),
    )


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
    return apply_sequential_bbm_to_details(db, route, details)


def sync_sale_from_route(db: Session, route: DeliveryRoute) -> Sale:
    assert_route_tariffs_complete(db, route)
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
        apply_route_fees_from_payload(db, sale, route.vehicle_type_id, route)
        db.execute(delete(SaleDetail).where(SaleDetail.sale_id == sale.id))
    else:
        now = datetime.now()
        prefix = now.strftime("UJ%y%m")
        last_sale = db.scalar(
            select(Sale.sale_no)
            .where(Sale.sale_no.like(f"{prefix}%"))
            .order_by(Sale.sale_no.desc())
            .limit(1)
        )
        if last_sale and len(last_sale) == 10:
            try:
                counter = int(last_sale[6:]) + 1
            except ValueError:
                counter = 1
        else:
            counter = 1
        
        sale = Sale(
            sale_no=f"{prefix}{counter:04d}",
            date=route.date,
            vehicle_id=None,
            driver_id=route.driver_id,
            delivery_route_id=route.id,
            remarks=route.remarks,
            extra_uang_jalan=0,
        )
        apply_route_fees_from_payload(db, sale, route.vehicle_type_id, route)
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


def sync_sales_for_period(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_type_id: int | None = None,
) -> dict:
    """Buat/perbarui uang jalan untuk semua rute dalam periode (kecuali sudah dikunci Finance)."""
    stmt = (
        select(DeliveryRoute)
        .options(selectinload(DeliveryRoute.stops))
        .order_by(DeliveryRoute.date.asc(), DeliveryRoute.id.asc())
    )
    if from_date:
        stmt = stmt.where(DeliveryRoute.date >= from_date)
    if to_date:
        stmt = stmt.where(DeliveryRoute.date <= to_date)
    if vehicle_type_id:
        stmt = stmt.where(DeliveryRoute.vehicle_type_id == vehicle_type_id)

    routes = db.scalars(stmt).all()
    created = 0
    updated = 0
    skipped_locked = 0
    skipped_errors: list[dict] = []

    for route in routes:
        existing = db.scalar(select(Sale).where(Sale.delivery_route_id == route.id))
        if existing and sale_finance_locked(existing):
            skipped_locked += 1
            continue
        try:
            had_sale = existing is not None
            sync_sale_from_route(db, route)
            if had_sale:
                updated += 1
            else:
                created += 1
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            skipped_errors.append(
                {"route_id": route.id, "route_no": route.route_no, "reason": detail}
            )

    return {
        "total_routes": len(routes),
        "created": created,
        "updated": updated,
        "synced": created + updated,
        "skipped_locked": skipped_locked,
        "skipped_errors": skipped_errors,
    }


def resync_sales_for_customer(db: Session, customer_id: int) -> int:
    """Hitung ulang uang jalan rute yang memuat customer ini (kecuali sudah dibayar Finance)."""
    route_ids = db.scalars(
        select(DeliveryRouteStop.route_id)
        .where(DeliveryRouteStop.customer_id == customer_id)
        .distinct()
    ).all()
    synced = 0
    for route_id in route_ids:
        route = db.scalar(
            select(DeliveryRoute)
            .where(DeliveryRoute.id == route_id)
            .options(selectinload(DeliveryRoute.stops))
        )
        if not route:
            continue
        sale = db.scalar(select(Sale).where(Sale.delivery_route_id == route_id))
        if not sale or sale_finance_locked(sale):
            continue
        try:
            sync_sale_from_route(db, route)
            synced += 1
        except HTTPException:
            continue
    return synced


def refresh_customer_tariff_in_sales(db: Session, customer_id: int) -> int:
    """Perbarui nominal uang jalan customer ini saja di sale rute terkait (tanpa validasi customer lain)."""
    route_ids = db.scalars(
        select(DeliveryRouteStop.route_id)
        .where(DeliveryRouteStop.customer_id == customer_id)
        .distinct()
    ).all()
    updated = 0
    for route_id in route_ids:
        route = db.scalar(select(DeliveryRoute).where(DeliveryRoute.id == route_id))
        if not route:
            continue
        sale = db.scalar(select(Sale).where(Sale.delivery_route_id == route_id))
        if not sale or sale_finance_locked(sale):
            continue
        try:
            vehicle_type_id = resolve_vehicle_type_id(db, route)
        except HTTPException:
            continue
        amount = tariff_amount_for_customer(db, customer_id, vehicle_type_id)
        rows = db.scalars(
            select(SaleDetail).where(
                SaleDetail.sale_id == sale.id,
                SaleDetail.customer_id == customer_id,
            )
        ).all()
        for row in rows:
            row.amount = amount
            row.vehicle_type_id = vehicle_type_id
            updated += 1
        apply_sequential_bbm_to_sale(db, route, sale)
    return updated


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
    seen: set[tuple[int, str]] = set()
    for idx, stop_item in enumerate(stops):
        customer_id = stop_item.customer_id
        so_key = (stop_item.description or "").strip().casefold()
        stop_key = (customer_id, so_key)
        if stop_key in seen:
            raise HTTPException(
                status_code=400,
                detail="Customer dengan nomor SO yang sama tidak boleh duplikat pada rute",
            )
        seen.add(stop_key)
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
