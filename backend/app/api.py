from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, exists, func, nulls_last, select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_api_access, require_permission
from app.sale_lock import (
    MSG_ROUTE_FINANCE_PAID,
    assert_route_editable,
    assert_sale_editable,
    route_sale,
    sale_finance_locked,
)
from app.roles import Role
from app.db import get_db
from app.money_utils import compute_uang_jalan_totals
from app.models import (
    BbmMaster,
    CashDisbursement,
    Customer,
    CustomerVehicleTariff,
    DeliveryRoute,
    DeliveryRouteStop,
    Driver,
    Vehicle,
    VehicleBrand,
    VehicleType,
    Sale,
    SaleDetail,
    User,
    TollSection,
    TollSectionRate,
    TollGolongan,
    WarehouseSetting,
    AppSetting,
)
from app.delivery_route_service import (
    format_stop_items_summary,
    replace_route_stops,
    resync_sales_for_customer,
    sync_sale_from_route,
    sync_sales_for_period,
)
from app.reports_service import (
    customer_summary,
    delivery_route_report,
    disbursement_detail,
    driver_summary,
)
from app.routing_service import (
    calculate_route,
    estimate_tolls_by_vehicle,
    geocode_address,
    get_toll_reference,
    serialize_toll_sections,
    _default_sections_from_settings,
)
from app.schemas import (
    CashDisbursementCreate,
    CashDisbursementOut,
    CustomerCreate,
    CustomerOut,
    CustomerListOut,
    CustomerBulkImport,
    CustomerSummaryRow,
    CustomerTariffItem,
    CustomerTariffOut,
    DisbursementDetailRow,
    DriverCreate,
    DriverOut,
    DriverSummaryRow,
    VehicleBrandCreate,
    VehicleBrandOut,
    BbmCreate,
    BbmOut,
    VehicleCreate,
    VehicleOut,
    VehicleTypeCreate,
    VehicleTypeOut,
    SaleCreate,
    SaleOut,
    SaleDetailOut,
    DeliveryRouteCreate,
    DeliveryRouteBulkSyncOut,
    DeliveryRouteOut,
    DeliveryRouteReportOut,
    DeliveryRouteStopLineOut,
    DeliveryRouteStopOut,
    WarehouseOut,
    WarehouseUpdate,
    RouteProcessRequest,
    RouteProcessOut,
    RoutePoint,
    VehicleTollEstimate,
    GeocodeRequest,
    GeocodeOut,
    TollSectionCreate,
    TollSectionUpdate,
    TollSectionOut,
    TollSectionRateOut,
    TollGolonganCreate,
    TollGolonganUpdate,
    TollGolonganOut,
    TollReferenceOut,
    AppSettingOut,
    AppSettingUpdate,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_api_access)])


def _load_active_toll_sections(db: Session) -> list[dict]:
    rows = db.scalars(
        select(TollSection)
        .options(
            selectinload(TollSection.rates).selectinload(TollSectionRate.golongan)
        )
        .where(TollSection.is_active.is_(True))
        .order_by(TollSection.sort_order.asc(), TollSection.id.asc())
    ).all()
    if not rows:
        return _default_sections_from_settings()
    return serialize_toll_sections(rows)


def _load_toll_sections_query():
    return (
        select(TollSection)
        .options(selectinload(TollSection.rates).selectinload(TollSectionRate.golongan))
        .order_by(TollSection.sort_order.asc(), TollSection.id.asc())
    )


def _golongan_out(obj: TollGolongan) -> TollGolonganOut:
    return TollGolonganOut(
        id=obj.id,
        name=obj.name,
        code=obj.code,
        description=obj.description,
        sort_order=obj.sort_order,
        is_active=obj.is_active,
    )


def _toll_section_out(obj: TollSection) -> TollSectionOut:
    sorted_rates = sorted(
        [r for r in obj.rates if r.golongan is not None],
        key=lambda r: (r.golongan.sort_order, r.golongan.code),
    )
    rates = [
        TollSectionRateOut(
            golongan_id=rate.golongan_id,
            golongan_name=rate.golongan.name,
            golongan_code=rate.golongan.code,
            rate=float(rate.rate),
        )
        for rate in sorted_rates
    ]
    return TollSectionOut(
        id=obj.id,
        name=obj.name,
        length_km=float(obj.length_km),
        sort_order=obj.sort_order,
        is_active=obj.is_active,
        rates=rates,
    )


def _sync_legacy_section_amounts(obj: TollSection) -> None:
    gol23 = next((float(r.rate) for r in obj.rates if r.golongan and r.golongan.code == "II"), None)
    if gol23 is None:
        gol23 = next((float(r.rate) for r in obj.rates if r.golongan and r.golongan.code == "III"), 0)
    gol45 = next((float(r.rate) for r in obj.rates if r.golongan and r.golongan.code == "IV"), None)
    if gol45 is None:
        gol45 = next((float(r.rate) for r in obj.rates if r.golongan and r.golongan.code == "V"), 0)
    obj.gol23 = gol23 or 0
    obj.gol45 = gol45 or 0


def _replace_section_rates(db: Session, section: TollSection, rate_items: list) -> None:
    db.execute(delete(TollSectionRate).where(TollSectionRate.section_id == section.id))
    db.flush()
    for item in rate_items:
        golongan_id = item.golongan_id if hasattr(item, "golongan_id") else item["golongan_id"]
        rate_value = item.rate if hasattr(item, "rate") else item["rate"]
        golongan = db.get(TollGolongan, golongan_id)
        if not golongan:
            raise HTTPException(status_code=400, detail=f"Golongan id {golongan_id} tidak ditemukan")
        db.add(
            TollSectionRate(
                section_id=section.id,
                golongan_id=golongan_id,
                rate=rate_value,
            )
        )
    db.flush()
    db.refresh(section, attribute_names=["rates"])
    for rate in section.rates:
        db.refresh(rate, attribute_names=["golongan"])
    _sync_legacy_section_amounts(section)


def _vehicle_type_out(obj: VehicleType) -> VehicleTypeOut:
    gol = obj.toll_golongan
    bbm = obj.bbm
    return VehicleTypeOut(
        id=obj.id,
        name=obj.name,
        toll_golongan_id=obj.toll_golongan_id,
        toll_golongan_name=gol.name if gol else None,
        toll_golongan_code=gol.code if gol else None,
        bbm_id=obj.bbm_id,
        bbm_name=bbm.name if bbm else None,
        bbm_price=float(bbm.price) if bbm else None,
        km_per_liter=float(obj.km_per_liter) if obj.km_per_liter is not None else None,
        uang_mel=float(obj.uang_mel or 0),
        created_at=obj.created_at,
    )


def _validate_toll_golongan_id(db: Session, toll_golongan_id: int | None) -> None:
    if toll_golongan_id is None:
        return
    if not db.get(TollGolongan, toll_golongan_id):
        raise HTTPException(status_code=400, detail="Golongan tol tidak ditemukan")


def _validate_bbm_id(db: Session, bbm_id: int | None) -> None:
    if bbm_id is None:
        return
    if not db.get(BbmMaster, bbm_id):
        raise HTTPException(status_code=400, detail="BBM tidak ditemukan")


def _vehicle_out(obj: Vehicle) -> VehicleOut:
    return VehicleOut(
        id=obj.id,
        plate_number=obj.plate_number,
        brand_id=obj.brand_id,
        type_id=obj.type_id,
        type_name=obj.type.name if obj.type else None,
        created_at=obj.created_at,
    )


def _load_vehicles_query():
    return (
        select(Vehicle)
        .options(selectinload(Vehicle.type))
        .order_by(Vehicle.plate_number.asc())
    )


def _unique_violation_to_409(e: Exception) -> HTTPException:
    msg = str(e)
    # pg8000 stores constraint info in orig_args dict or nested exception
    orig = getattr(e, "orig", None)
    if orig is not None:
        msg = str(orig)
    if "customers_code_key" in msg:
        return HTTPException(status_code=409, detail="Kode customer sudah dipakai. Gunakan kode lain.")
    if "customers_name_key" in msg:
        return HTTPException(status_code=409, detail="Nama customer sudah ada di database. Hubungi admin jika ini tidak seharusnya.")
    if "uq_customer_vehicle_type" in msg:
        return HTTPException(status_code=409, detail="Tarif jenis kendaraan duplikat. Coba ulangi.")
    if "vehicle_brands" in msg:
        return HTTPException(status_code=409, detail="Merek kendaraan sudah ada.")
    if "vehicle_types" in msg:
        return HTTPException(status_code=409, detail="Jenis kendaraan sudah ada.")
    if "vehicles" in msg and "plate_number" in msg:
        return HTTPException(status_code=409, detail="Nomor plat kendaraan sudah terdaftar.")
    if "drivers" in msg:
        return HTTPException(status_code=409, detail="Nama sopir sudah ada.")
    if "duplicate key" in msg.lower() or "23505" in msg:
        return HTTPException(status_code=409, detail=f"Data duplikat — sudah ada di database. ({msg[:200]})")
    return HTTPException(status_code=409, detail=msg)


def _tariff_uang_jalan(row: CustomerTariffItem) -> float:
    component_total = row.bbm + row.tol + row.uang_mel + row.parkir + row.lain_lain
    if component_total > 0:
        return component_total
    return row.uang_jalan


def _normalize_customer_code(code: str | None) -> str:
    normalized = (code or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Kode customer wajib diisi.")
    return normalized


def _ensure_customer_code_unique(
    db: Session, code: str, exclude_customer_id: int | None = None
) -> None:
    stmt = select(Customer).where(func.lower(Customer.code) == code.lower())
    if exclude_customer_id is not None:
        stmt = stmt.where(Customer.id != exclude_customer_id)
    if db.scalar(stmt):
        raise HTTPException(
            status_code=409,
            detail="Kode customer sudah dipakai. Gunakan kode lain.",
        )


def _try_normalize_customer_code(code: str | None) -> str | None:
    try:
        return _normalize_customer_code(code)
    except HTTPException:
        return None


def _validate_tariffs(db: Session, tariffs: list[CustomerTariffItem]) -> None:
    seen: set[int] = set()
    for row in tariffs:
        if row.vehicle_type_id in seen:
            raise HTTPException(status_code=400, detail="Jenis kendaraan duplikat pada tarif")
        seen.add(row.vehicle_type_id)
        if not db.get(VehicleType, row.vehicle_type_id):
            raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")


def _replace_customer_tariffs(
    db: Session, customer_id: int, tariffs: list[CustomerTariffItem]
) -> None:
    db.execute(
        delete(CustomerVehicleTariff).where(CustomerVehicleTariff.customer_id == customer_id)
    )
    db.flush()
    for row in tariffs:
        if _tariff_uang_jalan(row) <= 0:
            continue
        total = _tariff_uang_jalan(row)
        db.add(
            CustomerVehicleTariff(
                customer_id=customer_id,
                vehicle_type_id=row.vehicle_type_id,
                bbm=row.bbm,
                tol=row.tol,
                uang_mel=row.uang_mel,
                parkir=row.parkir,
                lain_lain=row.lain_lain,
                uang_jalan=total,
            )
        )


def _serialize_customer(db: Session, customer: Customer) -> CustomerOut:
    rows = db.execute(
        select(CustomerVehicleTariff, VehicleType.name)
        .join(VehicleType, CustomerVehicleTariff.vehicle_type_id == VehicleType.id)
        .where(CustomerVehicleTariff.customer_id == customer.id)
        .order_by(VehicleType.name.asc())
    ).all()
    tariffs = [
        CustomerTariffOut(
            vehicle_type_id=tariff.vehicle_type_id,
            vehicle_type_name=type_name,
            bbm=float(tariff.bbm),
            tol=float(tariff.tol),
            uang_mel=float(tariff.uang_mel or 0),
            parkir=float(tariff.parkir),
            lain_lain=float(tariff.lain_lain),
            uang_jalan=float(tariff.uang_jalan),
        )
        for tariff, type_name in rows
    ]
    return CustomerOut(
        id=customer.id,
        code=customer.code,
        name=customer.name,
        address=customer.address,
        kelurahan=customer.kelurahan,
        kecamatan=customer.kecamatan,
        city=customer.city,
        phone=customer.phone,
        email=customer.email,
        is_active=customer.is_active,
        force_toll=customer.force_toll,
        latitude=float(customer.latitude) if customer.latitude is not None else None,
        longitude=float(customer.longitude) if customer.longitude is not None else None,
        tariffs=tariffs,
        created_at=customer.created_at,
    )


def _serialize_customer_list(customer: Customer) -> CustomerListOut:
    return CustomerListOut(
        id=customer.id,
        code=customer.code,
        name=customer.name,
        phone=customer.phone,
        is_active=customer.is_active,
        kelurahan=customer.kelurahan,
        kecamatan=customer.kecamatan,
        city=customer.city,
        latitude=float(customer.latitude) if customer.latitude is not None else None,
        longitude=float(customer.longitude) if customer.longitude is not None else None,
        force_toll=customer.force_toll,
    )


@router.get("/customers", response_model=list[CustomerListOut])
def list_customers(db: Session = Depends(get_db)):
    customers = db.scalars(
        select(Customer).order_by(nulls_last(Customer.code.asc()), Customer.name.asc())
    ).all()
    return [_serialize_customer_list(c) for c in customers]


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    obj = db.get(Customer, customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    return _serialize_customer(db, obj)


@router.post("/customers/bulk", response_model=dict, status_code=201)
def bulk_create_customers(payload: CustomerBulkImport, db: Session = Depends(get_db)):
    imported = 0
    skipped = 0
    for item in payload.customers:
        code = _try_normalize_customer_code(item.code)
        if not code:
            skipped += 1
            continue
        existing_code = db.scalar(select(Customer).where(func.lower(Customer.code) == code.lower()))
        if existing_code:
            skipped += 1
            continue

        obj = Customer(
            code=code,
            name=item.name.strip(),
            address=item.address.strip() if item.address else None,
            kelurahan=item.kelurahan.strip() if item.kelurahan else None,
            kecamatan=item.kecamatan.strip() if item.kecamatan else None,
            city=item.city.strip() if item.city else None,
            phone=item.phone.strip() if item.phone else None,
            email=item.email.strip() if item.email else None,
            is_active=True,
            latitude=item.latitude,
            longitude=item.longitude,
        )
        db.add(obj)
        imported += 1

    if imported == 0 and skipped == 0:
        raise HTTPException(status_code=400, detail="Tidak ada baris valid untuk diimport.")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)

    return {"imported": imported, "skipped": skipped, "total": len(payload.customers)}


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    _validate_tariffs(db, payload.tariffs)
    code = _normalize_customer_code(payload.code)
    _ensure_customer_code_unique(db, code)
    obj = Customer(
        code=code,
        name=payload.name.strip(),
        address=payload.address.strip() if payload.address else None,
        kelurahan=payload.kelurahan.strip() if payload.kelurahan else None,
        kecamatan=payload.kecamatan.strip() if payload.kecamatan else None,
        city=payload.city.strip() if payload.city else None,
        phone=payload.phone.strip() if payload.phone else None,
        email=payload.email.strip() if payload.email else None,
        is_active=payload.is_active,
        force_toll=payload.force_toll,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(obj)
    try:
        db.flush()
        _replace_customer_tariffs(db, obj.id, payload.tariffs)
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_customer(db, obj)


@router.put("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerCreate, db: Session = Depends(get_db)):
    # Use with_for_update() to lock the customer row and prevent DELETE/INSERT race conditions
    # on tariffs if there are concurrent update requests.
    obj = db.execute(select(Customer).where(Customer.id == customer_id).with_for_update()).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")

    _validate_tariffs(db, payload.tariffs)
    code = _normalize_customer_code(payload.code)
    _ensure_customer_code_unique(db, code, exclude_customer_id=customer_id)
    obj.code = code
    obj.name = payload.name.strip()
    obj.address = payload.address.strip() if payload.address else None
    obj.kelurahan = payload.kelurahan.strip() if payload.kelurahan else None
    obj.kecamatan = payload.kecamatan.strip() if payload.kecamatan else None
    obj.city = payload.city.strip() if payload.city else None
    obj.phone = payload.phone.strip() if payload.phone else None
    obj.email = payload.email.strip() if payload.email else None
    obj.is_active = payload.is_active
    obj.force_toll = payload.force_toll
    obj.latitude = payload.latitude
    obj.longitude = payload.longitude

    try:
        _replace_customer_tariffs(db, obj.id, payload.tariffs)
        resync_sales_for_customer(db, obj.id)
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_customer(db, obj)


@router.delete("/customers/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    obj = db.get(Customer, customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    # Check if used in sales
    in_sales = db.scalar(
        select(func.count()).select_from(SaleDetail).where(SaleDetail.customer_id == customer_id)
    )
    if in_sales:
        raise HTTPException(
            status_code=409,
            detail="Customer masih dipakai di transaksi Uang Jalan. Hapus transaksi tersebut terlebih dahulu.",
        )
    # Check if used in cash disbursements
    in_disb = db.scalar(
        select(func.count()).select_from(CashDisbursement).where(CashDisbursement.customer_id == customer_id)
    )
    if in_disb:
        raise HTTPException(
            status_code=409,
            detail="Customer masih dipakai di pengeluaran kas. Hapus data tersebut terlebih dahulu.",
        )
    in_route = db.scalar(
        select(func.count())
        .select_from(DeliveryRouteStop)
        .where(DeliveryRouteStop.customer_id == customer_id)
    )
    if in_route:
        raise HTTPException(
            status_code=409,
            detail="Customer masih dipakai di rute pengiriman. Hapus dari rute atau hapus rute tersebut terlebih dahulu.",
        )
    # Tariffs will be cascade-deleted automatically
    db.delete(obj)
    db.commit()


@router.get("/vehicle-brands", response_model=list[VehicleBrandOut])
def list_vehicle_brands(db: Session = Depends(get_db)):
    return db.scalars(select(VehicleBrand).order_by(VehicleBrand.name.asc())).all()


@router.post("/vehicle-brands", response_model=VehicleBrandOut, status_code=201)
def create_vehicle_brand(payload: VehicleBrandCreate, db: Session = Depends(get_db)):
    obj = VehicleBrand(name=payload.name.strip())
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return obj


@router.put("/vehicle-brands/{brand_id}", response_model=VehicleBrandOut)
def update_vehicle_brand(
    brand_id: int, payload: VehicleBrandCreate, db: Session = Depends(get_db)
):
    obj = db.get(VehicleBrand, brand_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Merek tidak ditemukan")
    obj.name = payload.name.strip()
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return obj


@router.delete("/vehicle-brands/{brand_id}", status_code=204)
def delete_vehicle_brand(brand_id: int, db: Session = Depends(get_db)):
    obj = db.get(VehicleBrand, brand_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Merek tidak ditemukan")
    in_use = db.scalar(
        select(func.count()).select_from(Vehicle).where(Vehicle.brand_id == brand_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Merek masih dipakai kendaraan. Ubah atau hapus kendaraan tersebut dulu.",
        )
    db.delete(obj)
    db.commit()


@router.get("/bbm", response_model=list[BbmOut])
def list_bbm(db: Session = Depends(get_db)):
    return db.scalars(select(BbmMaster).order_by(BbmMaster.name.asc())).all()


@router.post("/bbm", response_model=BbmOut, status_code=201)
def create_bbm(payload: BbmCreate, db: Session = Depends(get_db)):
    obj = BbmMaster(name=payload.name.strip(), price=payload.price)
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.put("/bbm/{bbm_id}", response_model=BbmOut)
def update_bbm(bbm_id: int, payload: BbmCreate, db: Session = Depends(get_db)):
    obj = db.get(BbmMaster, bbm_id)
    if not obj:
        raise HTTPException(status_code=404, detail="BBM tidak ditemukan")
    obj.name = payload.name.strip()
    obj.price = payload.price
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.delete("/bbm/{bbm_id}", status_code=204)
def delete_bbm(bbm_id: int, db: Session = Depends(get_db)):
    obj = db.get(BbmMaster, bbm_id)
    if not obj:
        raise HTTPException(status_code=404, detail="BBM tidak ditemukan")
    in_use = db.scalar(
        select(func.count()).select_from(VehicleType).where(VehicleType.bbm_id == bbm_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="BBM masih dipakai jenis kendaraan. Ubah jenis kendaraan tersebut dulu.",
        )
    db.delete(obj)
    db.commit()


def _load_vehicle_types_query():
    return (
        select(VehicleType)
        .options(
            selectinload(VehicleType.toll_golongan),
            selectinload(VehicleType.bbm),
        )
        .order_by(VehicleType.name.asc())
    )


@router.get("/vehicle-types", response_model=list[VehicleTypeOut])
def list_vehicle_types(db: Session = Depends(get_db)):
    rows = db.scalars(_load_vehicle_types_query()).all()
    return [_vehicle_type_out(row) for row in rows]


@router.post("/vehicle-types", response_model=VehicleTypeOut, status_code=201)
def create_vehicle_type(payload: VehicleTypeCreate, db: Session = Depends(get_db)):
    _validate_toll_golongan_id(db, payload.toll_golongan_id)
    _validate_bbm_id(db, payload.bbm_id)
    obj = VehicleType(
        name=payload.name.strip(),
        toll_golongan_id=payload.toll_golongan_id,
        bbm_id=payload.bbm_id,
        km_per_liter=payload.km_per_liter,
        uang_mel=payload.uang_mel,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    obj = db.scalar(_load_vehicle_types_query().where(VehicleType.id == obj.id))
    return _vehicle_type_out(obj)


@router.put("/vehicle-types/{type_id}", response_model=VehicleTypeOut)
def update_vehicle_type(
    type_id: int, payload: VehicleTypeCreate, db: Session = Depends(get_db)
):
    obj = db.get(VehicleType, type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Jenis tidak ditemukan")
    _validate_toll_golongan_id(db, payload.toll_golongan_id)
    _validate_bbm_id(db, payload.bbm_id)
    obj.name = payload.name.strip()
    obj.toll_golongan_id = payload.toll_golongan_id
    obj.bbm_id = payload.bbm_id
    obj.km_per_liter = payload.km_per_liter
    obj.uang_mel = payload.uang_mel
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    obj = db.scalar(_load_vehicle_types_query().where(VehicleType.id == type_id))
    return _vehicle_type_out(obj)


@router.delete("/vehicle-types/{type_id}", status_code=204)
def delete_vehicle_type(type_id: int, db: Session = Depends(get_db)):
    obj = db.get(VehicleType, type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Jenis tidak ditemukan")
    in_use_vehicle = db.scalar(
        select(func.count()).select_from(Vehicle).where(Vehicle.type_id == type_id)
    )
    in_use_customer = db.scalar(
        select(func.count())
        .select_from(CustomerVehicleTariff)
        .where(CustomerVehicleTariff.vehicle_type_id == type_id)
    )
    in_use_disb = db.scalar(
        select(func.count())
        .select_from(CashDisbursement)
        .where(CashDisbursement.vehicle_type_id == type_id)
    )
    if in_use_vehicle or in_use_customer or in_use_disb:
        raise HTTPException(
            status_code=409,
            detail="Jenis masih dipakai kendaraan atau pengeluaran. Hapus data terkait dulu.",
        )
    db.delete(obj)
    db.commit()


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(db: Session = Depends(get_db)):
    rows = db.scalars(_load_vehicles_query()).all()
    return [_vehicle_out(row) for row in rows]


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    if not db.get(VehicleBrand, payload.brand_id):
        raise HTTPException(status_code=400, detail="Merek tidak ditemukan")
    if payload.type_id and not db.get(VehicleType, payload.type_id):
        raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")
    obj = Vehicle(
        plate_number=payload.plate_number.strip(),
        brand_id=payload.brand_id,
        type_id=payload.type_id,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    obj = db.scalar(_load_vehicles_query().where(Vehicle.id == obj.id))
    return _vehicle_out(obj)


@router.put("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int, payload: VehicleCreate, db: Session = Depends(get_db)
):
    obj = db.get(Vehicle, vehicle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    if not db.get(VehicleBrand, payload.brand_id):
        raise HTTPException(status_code=400, detail="Merek tidak ditemukan")
    if payload.type_id and not db.get(VehicleType, payload.type_id):
        raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")
    obj.plate_number = payload.plate_number.strip()
    obj.brand_id = payload.brand_id
    obj.type_id = payload.type_id
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    obj = db.scalar(_load_vehicles_query().where(Vehicle.id == vehicle_id))
    return _vehicle_out(obj)


@router.delete("/vehicles/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    obj = db.get(Vehicle, vehicle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    db.delete(obj)
    db.commit()


@router.get("/drivers", response_model=list[DriverOut])
def list_drivers(db: Session = Depends(get_db)):
    return db.scalars(select(Driver).order_by(Driver.name.asc())).all()


@router.post("/drivers", response_model=DriverOut, status_code=201)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db)):
    obj = Driver(
        name=payload.name.strip(), 
        phone=(payload.phone.strip() if payload.phone else None),
        bank_name=(payload.bank_name.strip() if payload.bank_name else None),
        bank_account=(payload.bank_account.strip() if payload.bank_account else None),
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return obj


@router.put("/drivers/{driver_id}", response_model=DriverOut)
def update_driver(
    driver_id: int, payload: DriverCreate, db: Session = Depends(get_db)
):
    obj = db.get(Driver, driver_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Supir tidak ditemukan")
    obj.name = payload.name.strip()
    obj.phone = payload.phone.strip() if payload.phone else None
    obj.bank_name = payload.bank_name.strip() if payload.bank_name else None
    obj.bank_account = payload.bank_account.strip() if payload.bank_account else None
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return obj


@router.delete("/drivers/{driver_id}", status_code=204)
def delete_driver(driver_id: int, db: Session = Depends(get_db)):
    obj = db.get(Driver, driver_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Supir tidak ditemukan")
    in_sale = db.scalar(select(exists().where(Sale.driver_id == driver_id)))
    in_route = db.scalar(select(exists().where(DeliveryRoute.driver_id == driver_id)))
    if in_sale or in_route:
        raise HTTPException(
            status_code=409,
            detail="Supir masih dipakai di transaksi penjualan dan tidak bisa dihapus",
        )
    db.delete(obj)
    db.commit()


def _serialize_disbursement(db: Session, obj: CashDisbursement) -> CashDisbursementOut:
    customer = db.get(Customer, obj.customer_id)
    vtype = db.get(VehicleType, obj.vehicle_type_id) if obj.vehicle_type_id else None
    return CashDisbursementOut(
        id=obj.id,
        customer_id=obj.customer_id,
        customer_name=customer.name if customer else None,
        vehicle_type_id=obj.vehicle_type_id,
        vehicle_type_name=vtype.name if vtype else None,
        amount=float(obj.amount),
        description=obj.description,
        disbursed_at=obj.disbursed_at,
        created_at=obj.created_at,
    )


@router.get("/cash-disbursements", response_model=list[CashDisbursementOut])
def list_cash_disbursements(db: Session = Depends(get_db)):
    items = db.scalars(
        select(CashDisbursement).order_by(CashDisbursement.disbursed_at.desc())
    ).all()
    return [_serialize_disbursement(db, item) for item in items]


@router.get("/reports/by-driver", response_model=list[DriverSummaryRow])
def report_by_driver(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    return driver_summary(db, from_date, to_date)


@router.get("/reports/by-customer", response_model=list[CustomerSummaryRow])
def report_by_customer(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    return customer_summary(db, from_date, to_date)


@router.get("/reports/disbursements", response_model=list[DisbursementDetailRow])
def report_disbursements(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    customer_id: int | None = None,
    db: Session = Depends(get_db),
):
    return disbursement_detail(db, from_date, to_date, customer_id=customer_id)


@router.get("/reports/delivery-details", response_model=list[DisbursementDetailRow], include_in_schema=False)
def report_delivery_details_legacy(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    customer_id: int | None = None,
    db: Session = Depends(get_db),
):
    return disbursement_detail(db, from_date, to_date, customer_id=customer_id)


@router.get("/reports/sales")
def report_sales(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    driver_id: int | None = None,
    customer_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Sale)
        .options(selectinload(Sale.details))
        .order_by(Sale.date.desc(), Sale.created_at.desc())
    )
    if from_date:
        stmt = stmt.where(Sale.date >= from_date)
    if to_date:
        stmt = stmt.where(Sale.date <= to_date)
    if driver_id:
        stmt = stmt.where(Sale.driver_id == driver_id)
    if customer_id:
        stmt = stmt.where(
            Sale.id.in_(
                select(SaleDetail.sale_id).where(SaleDetail.customer_id == customer_id)
            )
        )

    sales = db.scalars(stmt).all()
    results = []
    for s in sales:
        vehicle = db.get(Vehicle, s.vehicle_id)
        driver = db.get(Driver, s.driver_id)
        detail_rows = []
        for d in s.details:
            cust = db.get(Customer, d.customer_id)
            vt = db.get(VehicleType, d.vehicle_type_id) if d.vehicle_type_id else None
            detail_rows.append({
                "customer_name": cust.name if cust else "-",
                "vehicle_type_name": vt.name if vt else "-",
                "amount": float(d.amount),
            })
        amounts = [d["amount"] for d in detail_rows if d["amount"] > 0]
        max_nominal = max(amounts) if amounts else 0
        extra = float(s.extra_uang_jalan or 0)
        multi = len(detail_rows) > 1
        base_uang_jalan = max_nominal if multi else (detail_rows[0]["amount"] if detail_rows else 0)
        totals = compute_uang_jalan_totals(base_uang_jalan, extra)

        results.append({
            "id": s.id,
            "sale_no": s.sale_no,
            "date": s.date.isoformat(),
            "vehicle_plate": vehicle.plate_number if vehicle else "-",
            "driver_name": driver.name if driver else "-",
            "remarks": s.remarks,
            "customers": ", ".join(d["customer_name"] for d in detail_rows),
            "vehicle_type": ", ".join(set(d["vehicle_type_name"] for d in detail_rows)),
            "uang_jalan": base_uang_jalan,
            "extra_uang_jalan": extra,
            "subtotal_uang_jalan": totals["subtotal"],
            "rounding_uang_jalan": totals["rounding"],
            "total_uang_jalan": totals["total"],
            "detail_count": len(detail_rows),
        })
    return results


@router.get("/reports/delivery-routes", response_model=DeliveryRouteReportOut)
def report_delivery_routes(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    vehicle_type_id: int | None = None,
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
):
    return delivery_route_report(
        db,
        from_date=from_date,
        to_date=to_date,
        vehicle_type_id=vehicle_type_id,
        vehicle_id=vehicle_id,
    )


@router.post("/cash-disbursements", response_model=CashDisbursementOut, status_code=201)
def create_cash_disbursement(payload: CashDisbursementCreate, db: Session = Depends(get_db)):
    if not db.get(Customer, payload.customer_id):
        raise HTTPException(status_code=400, detail="Customer tidak ditemukan")
    if payload.vehicle_type_id and not db.get(VehicleType, payload.vehicle_type_id):
        raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")
    obj = CashDisbursement(
        customer_id=payload.customer_id,
        vehicle_type_id=payload.vehicle_type_id,
        amount=payload.amount,
        description=payload.description,
        disbursed_at=payload.disbursed_at or datetime.now(timezone.utc),
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_disbursement(db, obj)


def _serialize_sale(db: Session, obj: Sale) -> SaleOut:
    vehicle = db.get(Vehicle, obj.vehicle_id) if obj.vehicle_id else None
    driver = db.get(Driver, obj.driver_id) if obj.driver_id else None
    details = []
    for d in obj.details:
        cust = db.get(Customer, d.customer_id)
        vtype = db.get(VehicleType, d.vehicle_type_id) if d.vehicle_type_id else None
        details.append(
            SaleDetailOut(
                id=d.id,
                customer_id=d.customer_id,
                customer_name=cust.name if cust else None,
                vehicle_type_id=d.vehicle_type_id,
                vehicle_type_name=vtype.name if vtype else None,
                amount=float(d.amount),
                created_at=d.created_at,
            )
        )
    route_no = None
    if obj.delivery_route_id:
        route = db.get(DeliveryRoute, obj.delivery_route_id)
        route_no = route.route_no if route else None

    paid_by = None
    if obj.finance_paid_by:
        approver = db.get(User, obj.finance_paid_by)
        paid_by = approver.full_name if approver else None

    return SaleOut(
        id=obj.id,
        sale_no=obj.sale_no,
        date=obj.date,
        vehicle_id=obj.vehicle_id,
        vehicle_plate=vehicle.plate_number if vehicle else None,
        driver_id=obj.driver_id,
        driver_name=driver.name if driver else None,
        driver_phone=driver.phone if driver else None,
        driver_bank_name=driver.bank_name if driver else None,
        driver_bank_account=driver.bank_account if driver else None,
        delivery_route_id=obj.delivery_route_id,
        route_no=route_no,
        remarks=obj.remarks,
        extra_uang_jalan=float(obj.extra_uang_jalan or 0),
        details=details,
        is_finance_paid=sale_finance_locked(obj),
        finance_paid_at=obj.finance_paid_at,
        finance_paid_by_name=paid_by,
        created_at=obj.created_at,
    )


def _serialize_delivery_route(db: Session, route: DeliveryRoute) -> DeliveryRouteOut:
    vehicle = db.get(Vehicle, route.vehicle_id) if route.vehicle_id else None
    vehicle_type = db.get(VehicleType, route.vehicle_type_id)
    driver = db.get(Driver, route.driver_id) if route.driver_id else None
    sale = db.scalar(select(Sale).where(Sale.delivery_route_id == route.id))
    stops_out: list[DeliveryRouteStopOut] = []
    for stop in sorted(route.stops, key=lambda s: s.sort_order):
        cust = db.get(Customer, stop.customer_id)
        lines_out = [
            DeliveryRouteStopLineOut(
                id=line.id,
                item_name=line.item_name,
                quantity=float(line.quantity),
                sort_order=line.sort_order,
            )
            for line in sorted(stop.lines, key=lambda ln: ln.sort_order)
        ]
        stops_out.append(
            DeliveryRouteStopOut(
                id=stop.id,
                customer_id=stop.customer_id,
                customer_name=cust.name if cust else None,
                sort_order=stop.sort_order,
                description=stop.description,
                entity_code=stop.entity_code,
                latitude=float(cust.latitude) if cust and cust.latitude is not None else None,
                longitude=float(cust.longitude) if cust and cust.longitude is not None else None,
                items=lines_out,
            )
        )
    sale_vehicle_plate = None
    sale_driver_name = None
    if sale:
        sale_vehicle = db.get(Vehicle, sale.vehicle_id) if sale.vehicle_id else None
        sale_driver = db.get(Driver, sale.driver_id) if sale.driver_id else None
        sale_vehicle_plate = sale_vehicle.plate_number if sale_vehicle else None
        sale_driver_name = sale_driver.name if sale_driver else None

    return DeliveryRouteOut(
        id=route.id,
        route_no=route.route_no,
        date=route.date,
        vehicle_type_id=route.vehicle_type_id,
        vehicle_type_name=vehicle_type.name if vehicle_type else None,
        vehicle_id=route.vehicle_id,
        vehicle_plate=vehicle.plate_number if vehicle else None,
        driver_id=route.driver_id,
        driver_name=driver.name if driver else None,
        driver_phone=driver.phone if driver else None,
        remarks=route.remarks,
        ritase=route.ritpiase,
        stops=stops_out,
        sale_id=sale.id if sale else None,
        sale_no=sale.sale_no if sale else None,
        sale_vehicle_plate=sale_vehicle_plate,
        sale_driver_name=sale_driver_name,
        is_finance_paid=sale_finance_locked(sale),
        finance_paid_at=sale.finance_paid_at if sale else None,
        created_at=route.created_at,
    )


def _load_route(db: Session, route_id: int) -> DeliveryRoute:
    route = db.scalar(
        select(DeliveryRoute)
        .where(DeliveryRoute.id == route_id)
        .options(
            selectinload(DeliveryRoute.stops).selectinload(DeliveryRouteStop.lines),
        )
    )
    if not route:
        raise HTTPException(status_code=404, detail="Rute pengiriman tidak ditemukan")
    return route


@router.get("/sales", response_model=list[SaleOut])
def list_sales(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    sale_no: str | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(Sale)
    if from_date:
        stmt = stmt.where(Sale.date >= from_date)
    if to_date:
        stmt = stmt.where(Sale.date <= to_date)
    if sale_no:
        stmt = stmt.outerjoin(DeliveryRoute).where(
            (Sale.sale_no.ilike(f"%{sale_no}%")) |
            (DeliveryRoute.route_no.ilike(f"%{sale_no}%"))
        )
    stmt = stmt.order_by(Sale.date.desc(), Sale.created_at.desc())
    sales = db.scalars(stmt).all()
    return [_serialize_sale(db, s) for s in sales]


@router.post("/sales", response_model=SaleOut, status_code=201)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    if not payload.vehicle_id:
        raise HTTPException(status_code=400, detail="Pilih kendaraan terlebih dahulu.")
    if not db.get(Vehicle, payload.vehicle_id):
        raise HTTPException(status_code=400, detail="Kendaraan tidak ditemukan")
    if payload.driver_id is not None and not db.get(Driver, payload.driver_id):
        raise HTTPException(status_code=400, detail="Sopir tidak ditemukan")
    
    # Generate sale_no if not provided
    sale_no = payload.sale_no
    if not sale_no:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        sale_no = f"SL-{timestamp}"
    
    obj = Sale(
        sale_no=sale_no,
        date=payload.date,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        remarks=payload.remarks,
        extra_uang_jalan=payload.extra_uang_jalan,
    )
    db.add(obj)
    db.flush()

    for d in payload.details:
        if not db.get(Customer, d.customer_id):
            raise HTTPException(status_code=400, detail=f"Customer {d.customer_id} tidak ditemukan")
        if not db.get(VehicleType, d.vehicle_type_id):
            raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")
        db.add(
            SaleDetail(
                sale_id=obj.id,
                customer_id=d.customer_id,
                vehicle_type_id=d.vehicle_type_id,
                amount=d.amount,
            )
        )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_sale(db, obj)


@router.get("/sales/{sale_id}", response_model=SaleOut)
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")
    return _serialize_sale(db, obj)


@router.post("/sales/{sale_id}/finance-approve", response_model=SaleOut)
def finance_approve_sale(
    sale_id: int,
    user: User = Depends(require_permission("sales:write")),
    db: Session = Depends(get_db),
):
    if user.role not in (Role.ADMIN.value, Role.FINANCE.value):
        raise HTTPException(
            status_code=403,
            detail="Hanya Finance atau Admin yang dapat menyetujui pembayaran uang jalan.",
        )
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")
    if sale_finance_locked(obj):
        raise HTTPException(status_code=400, detail="Pembayaran uang jalan sudah disetujui.")
    if not obj.vehicle_id or not obj.driver_id:
        raise HTTPException(
            status_code=400, 
            detail="Tidak dapat menyetujui transaksi: kendaraan dan sopir harus diisi terlebih dahulu."
        )
    obj.finance_paid_at = datetime.now(timezone.utc)
    obj.finance_paid_by = user.id
    db.commit()
    db.refresh(obj)
    return _serialize_sale(db, obj)


@router.post("/sales/{sale_id}/finance-unapprove", response_model=SaleOut)
def finance_unapprove_sale(
    sale_id: int,
    user: User = Depends(require_permission("sales:write")),
    db: Session = Depends(get_db),
):
    if user.role not in (Role.ADMIN.value, Role.FINANCE.value):
        raise HTTPException(
            status_code=403,
            detail="Hanya Finance atau Admin yang dapat membatalkan persetujuan pembayaran.",
        )
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")
    if not sale_finance_locked(obj):
        raise HTTPException(status_code=400, detail="Pembayaran uang jalan belum disetujui.")
    obj.finance_paid_at = None
    obj.finance_paid_by = None
    db.commit()
    db.refresh(obj)
    return _serialize_sale(db, obj)


@router.put("/sales/{sale_id}", response_model=SaleOut)
def update_sale(sale_id: int, payload: SaleCreate, db: Session = Depends(get_db)):
    db.execute(select(Sale).where(Sale.id == sale_id).with_for_update()).scalar_one_or_none()
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")

    assert_sale_editable(obj)

    if obj.delivery_route_id:
        route = db.get(DeliveryRoute, obj.delivery_route_id)
        if payload.date != obj.date:
            raise HTTPException(
                status_code=400,
                detail="Tanggal diubah lewat menu Rute Pengiriman.",
            )
        if route and route.driver_id is not None and payload.driver_id != route.driver_id:
            raise HTTPException(
                status_code=400,
                detail="Sopir rute diubah lewat menu Rute Pengiriman.",
            )
        if not payload.vehicle_id:
            raise HTTPException(status_code=400, detail="Pilih kendaraan terlebih dahulu.")
        if not db.get(Vehicle, payload.vehicle_id):
            raise HTTPException(status_code=400, detail="Kendaraan tidak ditemukan")
        route_customers = {
            s.customer_id
            for s in db.scalars(
                select(DeliveryRouteStop).where(DeliveryRouteStop.route_id == route.id)
            ).all()
        }
        payload_customers = {d.customer_id for d in payload.details}
        if route_customers != payload_customers:
            raise HTTPException(
                status_code=400,
                detail="Daftar customer mengikuti rute pengiriman. Ubah di menu Rute Pengiriman.",
            )
        obj.extra_uang_jalan = payload.extra_uang_jalan
        obj.remarks = payload.remarks
        obj.vehicle_id = payload.vehicle_id
        if payload.driver_id is not None:
            if not db.get(Driver, payload.driver_id):
                raise HTTPException(status_code=400, detail="Sopir tidak ditemukan")
            obj.driver_id = payload.driver_id
        else:
            obj.driver_id = None
        if payload.sale_no:
            obj.sale_no = payload.sale_no
        for detail in obj.details:
            match = next((x for x in payload.details if x.customer_id == detail.customer_id), None)
            if match:
                detail.amount = match.amount
                detail.vehicle_type_id = match.vehicle_type_id
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise _unique_violation_to_409(e)
        db.refresh(obj)
        return _serialize_sale(db, obj)

    if not payload.vehicle_id:
        raise HTTPException(status_code=400, detail="Pilih kendaraan terlebih dahulu.")
    if not db.get(Vehicle, payload.vehicle_id):
        raise HTTPException(status_code=400, detail="Kendaraan tidak ditemukan")
    if payload.driver_id is not None and not db.get(Driver, payload.driver_id):
        raise HTTPException(status_code=400, detail="Sopir tidak ditemukan")

    obj.date = payload.date
    obj.vehicle_id = payload.vehicle_id
    obj.driver_id = payload.driver_id
    obj.remarks = payload.remarks
    obj.extra_uang_jalan = payload.extra_uang_jalan
    if payload.sale_no:
        obj.sale_no = payload.sale_no

    db.execute(delete(SaleDetail).where(SaleDetail.sale_id == obj.id))
    for d in payload.details:
        if not db.get(Customer, d.customer_id):
            raise HTTPException(status_code=400, detail=f"Customer {d.customer_id} tidak ditemukan")
        if not db.get(VehicleType, d.vehicle_type_id):
            raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")
        db.add(
            SaleDetail(
                sale_id=obj.id,
                customer_id=d.customer_id,
                vehicle_type_id=d.vehicle_type_id,
                amount=d.amount,
            )
        )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_sale(db, obj)


@router.delete("/sales/{sale_id}", status_code=204)
def delete_sale(sale_id: int, db: Session = Depends(get_db)):
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")
    db.delete(obj)
    db.commit()


@router.get("/delivery-routes", response_model=list[DeliveryRouteOut])
def list_delivery_routes(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    vehicle_type_id: int | None = None,
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
):
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
    return [_serialize_delivery_route(db, r) for r in routes]


@router.post("/delivery-routes/sync-sales", response_model=DeliveryRouteBulkSyncOut)
def bulk_sync_sales_from_routes(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    vehicle_type_id: int | None = None,
    db: Session = Depends(get_db),
):
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="Tanggal awal tidak boleh setelah tanggal akhir.")
    if vehicle_type_id and not db.get(VehicleType, vehicle_type_id):
        raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")
    try:
        result = sync_sales_for_period(
            db,
            from_date=from_date,
            to_date=to_date,
            vehicle_type_id=vehicle_type_id,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    return result


@router.get("/delivery-routes/{route_id}", response_model=DeliveryRouteOut)
def get_delivery_route(route_id: int, db: Session = Depends(get_db)):
    return _serialize_delivery_route(db, _load_route(db, route_id))


@router.post("/delivery-routes", response_model=DeliveryRouteOut, status_code=201)
def create_delivery_route(payload: DeliveryRouteCreate, db: Session = Depends(get_db)):
    if not db.get(VehicleType, payload.vehicle_type_id):
        raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")

    route_no = payload.route_no
    if not route_no:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        route_no = f"RT-{timestamp}"

    obj = DeliveryRoute(
        route_no=route_no,
        date=payload.date,
        vehicle_type_id=payload.vehicle_type_id,
        remarks=payload.remarks,
        ritpiase=payload.ritase,
    )
    db.add(obj)
    db.flush()
    replace_route_stops(db, obj, payload.stops)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_delivery_route(db, _load_route(db, obj.id))


@router.put("/delivery-routes/{route_id}", response_model=DeliveryRouteOut)
def update_delivery_route(
    route_id: int, payload: DeliveryRouteCreate, db: Session = Depends(get_db)
):
    db.execute(select(DeliveryRoute).where(DeliveryRoute.id == route_id).with_for_update()).scalar_one_or_none()
    obj = _load_route(db, route_id)
    assert_route_editable(db, route_id)
    if not db.get(VehicleType, payload.vehicle_type_id):
        raise HTTPException(status_code=400, detail="Jenis kendaraan tidak ditemukan")

    obj.date = payload.date
    obj.vehicle_type_id = payload.vehicle_type_id
    obj.remarks = payload.remarks
    obj.ritpiase = payload.ritase
    if payload.route_no:
        obj.route_no = payload.route_no
    replace_route_stops(db, obj, payload.stops)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    return _serialize_delivery_route(db, _load_route(db, route_id))


@router.delete("/delivery-routes/{route_id}", status_code=204)
def delete_delivery_route(route_id: int, db: Session = Depends(get_db)):
    obj = _load_route(db, route_id)
    assert_route_editable(db, route_id)
    sale = route_sale(db, route_id)
    if sale:
        db.delete(sale)
    db.delete(obj)
    db.commit()


@router.post("/delivery-routes/{route_id}/generate-sale", response_model=SaleOut)
def generate_sale_from_route(route_id: int, db: Session = Depends(get_db)):
    route = _load_route(db, route_id)
    existing = route_sale(db, route_id)
    if existing and sale_finance_locked(existing):
        raise HTTPException(status_code=400, detail=MSG_ROUTE_FINANCE_PAID)
    try:
        sale = sync_sale_from_route(db, route)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(sale)
    return _serialize_sale(db, sale)


def _get_or_create_warehouse(db: Session) -> WarehouseSetting:
    obj = db.get(WarehouseSetting, 1)
    if not obj:
        obj = WarehouseSetting(id=1, name="Gudang Utama")
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj


def _warehouse_out(obj: WarehouseSetting) -> WarehouseOut:
    return WarehouseOut(
        id=obj.id,
        name=obj.name,
        address=obj.address,
        kelurahan=obj.kelurahan,
        kecamatan=obj.kecamatan,
        city=obj.city,
        latitude=float(obj.latitude) if obj.latitude is not None else None,
        longitude=float(obj.longitude) if obj.longitude is not None else None,
    )


@router.get("/warehouse", response_model=WarehouseOut)
def get_warehouse(db: Session = Depends(get_db)):
    return _warehouse_out(_get_or_create_warehouse(db))


@router.put("/warehouse", response_model=WarehouseOut)
def update_warehouse(payload: WarehouseUpdate, db: Session = Depends(get_db)):
    obj = _get_or_create_warehouse(db)
    obj.name = payload.name.strip()
    obj.address = payload.address.strip() if payload.address else None
    obj.kelurahan = payload.kelurahan.strip() if payload.kelurahan else None
    obj.kecamatan = payload.kecamatan.strip() if payload.kecamatan else None
    obj.city = payload.city.strip() if payload.city else None
    obj.latitude = payload.latitude
    obj.longitude = payload.longitude
    db.commit()
    db.refresh(obj)
    return _warehouse_out(obj)


@router.post("/warehouse/geocode", response_model=WarehouseOut)
def geocode_warehouse(db: Session = Depends(get_db)):
    obj = _get_or_create_warehouse(db)
    lat, lng = geocode_address(obj.address, obj.kelurahan, obj.kecamatan, obj.city, obj.name)
    obj.latitude = lat
    obj.longitude = lng
    db.commit()
    db.refresh(obj)
    return _warehouse_out(obj)


@router.post("/customers/{customer_id}/geocode", response_model=CustomerOut)
def geocode_customer(customer_id: int, db: Session = Depends(get_db)):
    obj = db.get(Customer, customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")
    lat, lng = geocode_address(obj.address, obj.kelurahan, obj.kecamatan, obj.city, obj.name)
    obj.latitude = lat
    obj.longitude = lng
    db.commit()
    db.refresh(obj)
    return _serialize_customer(db, obj)


@router.post("/routing/process", response_model=RouteProcessOut)
def process_route(payload: RouteProcessRequest, db: Session = Depends(get_db)):
    warehouse = _get_or_create_warehouse(db)

    try:
        origin_lat, origin_lng = (
            (float(warehouse.latitude), float(warehouse.longitude))
            if warehouse.latitude is not None and warehouse.longitude is not None
            else geocode_address(warehouse.address, warehouse.kelurahan, warehouse.kecamatan, warehouse.city, warehouse.name)
        )
    except HTTPException:
        raise HTTPException(
            status_code=400,
            detail="Koordinat gudang belum diatur. Isi alamat gudang di menu Gudang.",
        )

    customer = None
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer tidak ditemukan")

    if payload.latitude is not None and payload.longitude is not None:
        dest_lat, dest_lng = float(payload.latitude), float(payload.longitude)
    elif customer is not None:
        try:
            dest_lat, dest_lng = (
                (float(customer.latitude), float(customer.longitude))
                if customer.latitude is not None and customer.longitude is not None
                else geocode_address(customer.address, customer.kelurahan, customer.kecamatan, customer.city, customer.name)
            )
        except HTTPException:
            raise HTTPException(
                status_code=400,
                detail="Koordinat customer belum diatur. Isi alamat customer lalu geocode.",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Koordinat customer belum diatur. Isi alamat customer lalu geocode.",
        )

    if customer is not None:
        if customer.latitude is None or customer.longitude is None:
            customer.latitude = dest_lat
            customer.longitude = dest_lng
            db.commit()

    if warehouse.latitude is None or warehouse.longitude is None:
        warehouse.latitude = origin_lat
        warehouse.longitude = origin_lng
        db.commit()

    sections = _load_active_toll_sections(db)
    route = calculate_route(origin_lat, origin_lng, dest_lat, dest_lng, sections=sections, force_toll=payload.force_toll)

    if customer is not None:
        customer_name = customer.name
        customer_id = customer.id
        dest_address = ", ".join(p for p in [customer.address, customer.city] if p)
    else:
        customer_name = payload.name or "Partner"
        customer_id = None
        dest_address = None

    origin_address = ", ".join(p for p in [warehouse.address, warehouse.city] if p)

    vehicle_types = db.scalars(_load_vehicle_types_query()).all()
    toll_by_vehicle_raw = estimate_tolls_by_vehicle(
        route["distance_km"],
        [
            (
                vt.id,
                vt.name,
                vt.toll_golongan.code if vt.toll_golongan else None,
                vt.toll_golongan.name if vt.toll_golongan else None,
            )
            for vt in vehicle_types
        ],
        base_toll_idr=route["toll_idr"],
        toll_is_estimate=route["toll_is_estimate"],
        sections=sections,
    )
    if toll_by_vehicle_raw:
        route["toll_idr"] = toll_by_vehicle_raw[0]["toll_idr"]

    return RouteProcessOut(
        customer_id=customer_id,
        customer_name=customer_name,
        origin=RoutePoint(
            name=warehouse.name,
            address=origin_address or None,
            latitude=origin_lat,
            longitude=origin_lng,
        ),
        destination=RoutePoint(
            name=customer_name,
            address=dest_address,
            latitude=dest_lat,
            longitude=dest_lng,
        ),
        toll_by_vehicle=[VehicleTollEstimate(**item) for item in toll_by_vehicle_raw],
        **route,
    )


@router.get("/toll-golongan", response_model=list[TollGolonganOut])
def list_toll_golongan(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(TollGolongan).order_by(TollGolongan.sort_order.asc(), TollGolongan.id.asc())
    ).all()
    return [_golongan_out(row) for row in rows]


@router.post("/toll-golongan", response_model=TollGolonganOut, status_code=201)
def create_toll_golongan(payload: TollGolonganCreate, db: Session = Depends(get_db)):
    code = payload.code.strip().upper()
    obj = TollGolongan(
        name=payload.name.strip(),
        code=code,
        description=payload.description.strip() if payload.description else None,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return _golongan_out(obj)


@router.put("/toll-golongan/{golongan_id}", response_model=TollGolonganOut)
def update_toll_golongan(
    golongan_id: int, payload: TollGolonganUpdate, db: Session = Depends(get_db)
):
    obj = db.get(TollGolongan, golongan_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Golongan tol tidak ditemukan")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "code" in data and data["code"] is not None:
        data["code"] = data["code"].strip().upper()
    if "description" in data and data["description"] is not None:
        data["description"] = data["description"].strip() or None

    for key, value in data.items():
        setattr(obj, key, value)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return _golongan_out(obj)


@router.delete("/toll-golongan/{golongan_id}", status_code=204)
def delete_toll_golongan(golongan_id: int, db: Session = Depends(get_db)):
    obj = db.get(TollGolongan, golongan_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Golongan tol tidak ditemukan")
    in_use = db.scalar(
        select(exists().where(TollSectionRate.golongan_id == golongan_id))
    )
    if in_use:
        raise HTTPException(
            status_code=400,
            detail="Golongan masih dipakai di ruas tol. Hapus tarif ruas terlebih dahulu.",
        )
    db.delete(obj)
    db.commit()


@router.get("/toll-sections", response_model=list[TollSectionOut])
def list_toll_sections(db: Session = Depends(get_db)):
    rows = db.scalars(_load_toll_sections_query()).all()
    return [_toll_section_out(row) for row in rows]


@router.post("/toll-sections", response_model=TollSectionOut, status_code=201)
def create_toll_section(payload: TollSectionCreate, db: Session = Depends(get_db)):
    obj = TollSection(
        name=payload.name.strip(),
        length_km=payload.length_km,
        gol23=0,
        gol45=0,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(obj)
    db.flush()
    if payload.rates:
        _replace_section_rates(db, obj, payload.rates)
    else:
        _sync_legacy_section_amounts(obj)
    db.commit()
    db.refresh(obj)
    obj = db.scalar(_load_toll_sections_query().where(TollSection.id == obj.id))
    return _toll_section_out(obj)


@router.put("/toll-sections/{section_id}", response_model=TollSectionOut)
def update_toll_section(
    section_id: int, payload: TollSectionUpdate, db: Session = Depends(get_db)
):
    obj = db.scalar(_load_toll_sections_query().where(TollSection.id == section_id))
    if not obj:
        raise HTTPException(status_code=404, detail="Ruas tol tidak ditemukan")

    data = payload.model_dump(exclude_unset=True)
    rates = data.pop("rates", None)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(obj, key, value)
    if rates is not None:
        _replace_section_rates(db, obj, rates)
    else:
        _sync_legacy_section_amounts(obj)

    db.commit()
    obj = db.scalar(_load_toll_sections_query().where(TollSection.id == section_id))
    return _toll_section_out(obj)


@router.delete("/toll-sections/{section_id}", status_code=204)
def delete_toll_section(section_id: int, db: Session = Depends(get_db)):
    obj = db.get(TollSection, section_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Ruas tol tidak ditemukan")
    db.delete(obj)
    db.commit()


@router.get("/routing/toll-reference", response_model=TollReferenceOut)
def toll_reference(db: Session = Depends(get_db)):
    golongan_rows = db.scalars(
        select(TollGolongan)
        .where(TollGolongan.is_active.is_(True))
        .order_by(TollGolongan.sort_order.asc(), TollGolongan.id.asc())
    ).all()
    section_rows = db.scalars(
        _load_toll_sections_query().where(TollSection.is_active.is_(True))
    ).all()

    golongan_out = [_golongan_out(row) for row in golongan_rows]
    if section_rows:
        section_out = [_toll_section_out(row) for row in section_rows]
    else:
        section_out = [
            TollSectionOut(
                id=0,
                name=sec["name"],
                length_km=sec["length_km"],
                sort_order=i,
                is_active=True,
                rates=[
                    TollSectionRateOut(
                        golongan_id=0,
                        golongan_name="Gol II/III" if key == "gol23" else "Gol IV/V",
                        golongan_code="II" if key == "gol23" else "IV",
                        rate=sec[key],
                    )
                    for i, key in enumerate(["gol23", "gol45"], start=1)
                ],
            )
            for i, sec in enumerate(_default_sections_from_settings(), start=1)
        ]

    return TollReferenceOut(
        golongan=golongan_out,
        sections=section_out,
        note=get_toll_reference()["note"],
    )


@router.post("/geocode", response_model=GeocodeOut)
def geocode_point(payload: GeocodeRequest):
    lat, lng = geocode_address(payload.address, payload.kelurahan, payload.kecamatan, payload.city, payload.name)
    return GeocodeOut(latitude=lat, longitude=lng)


@router.get("/app-settings", response_model=AppSettingOut)
def get_app_setting(db: Session = Depends(get_db)):
    setting = db.scalars(select(AppSetting).limit(1)).first()
    if not setting:
        setting = AppSetting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


@router.put("/app-settings", response_model=AppSettingOut, dependencies=[Depends(require_permission("app_settings:write"))])
def update_app_setting(payload: AppSettingUpdate, db: Session = Depends(get_db)):
    setting = db.scalars(select(AppSetting).limit(1)).first()
    if not setting:
        setting = AppSetting()
        db.add(setting)
    
    update_data = payload.model_dump(exclude_unset=True)
    
    if "app_name" in update_data and update_data["app_name"] is not None:
        setting.app_name = update_data["app_name"].strip()
    if "app_subtitle" in update_data and update_data["app_subtitle"] is not None:
        setting.app_subtitle = update_data["app_subtitle"].strip()
    if "logo_base64" in update_data:
        setting.logo_base64 = update_data["logo_base64"]
    if "favicon_base64" in update_data:
        setting.favicon_base64 = update_data["favicon_base64"]

    db.commit()
    db.refresh(setting)
    return setting
