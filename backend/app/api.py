from __future__ import annotations

import json
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
    TollGate,
    TollGateFare,
    WarehouseSetting,
    AppSetting,
    UangMelMaster,
)
from app.toll_gate_service import (
    TOLL_NOTE_BPJT,
    build_manual_toll_breakdown,
    estimate_toll_bpjt_gates,
    refresh_gate_coordinates,
    serialize_gate_fare_context,
)
from app.bpjt_import_service import import_jabodetabek_all, import_jabodetabek_gate_matrices
from app.delivery_route_service import (
    format_stop_items_summary,
    replace_route_stops,
    refresh_customer_tariff_in_sales,
    sync_sale_from_route,
    sync_sales_for_period,
    customers_missing_tariff,
)
from app.reports_service import (
    customer_summary,
    delivery_route_report,
    disbursement_detail,
    driver_summary,
)
from app.routing_service import (
    VEHICLE_TOLL_CLASS,
    _match_toll_vehicle_key,
    calculate_route,
    collapse_sections_for_routing,
    estimate_tolls_by_vehicle,
    geocode_address,
    parse_coords_from_share,
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
    UangMelCreate,
    UangMelOut,
    VehicleCreate,
    VehicleOut,
    VehicleTypeCreate,
    VehicleTypeOut,
    SaleCreate,
    SaleOut,
    SaleDetailOut,
    SaleVoid,
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
    ManualTollBreakdownRequest,
    ManualTollBreakdownOut,
    RoutePoint,
    VehicleTollEstimate,
    GeocodeRequest,
    GeocodeFromShareRequest,
    GeocodeOut,
    TollSectionCreate,
    TollSectionUpdate,
    BpjtImportResultOut,
    BpjtGateImportResultOut,
    BpjtFullImportResultOut,
    TollGateCoordRefreshResultOut,
    TollSectionOut,
    TollSectionRateOut,
    TollGolonganCreate,
    TollGolonganUpdate,
    TollGateOut,
    TollGateCreate,
    TollGateUpdate,
    TollGateFareOut,
    TollGateFareCreate,
    TollGateFareUpdate,
    TollGolonganOut,
    TollReferenceOut,
    AppSettingOut,
    AppSettingUpdate,
    TollDataExport,
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
    return collapse_sections_for_routing(serialize_toll_sections(rows))


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
        network=obj.network,
        name=obj.name,
        origin_name=obj.origin_name,
        destination_name=obj.destination_name,
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


def _load_toll_gate_fare_context(db: Session) -> dict:
    gates = db.scalars(
        select(TollGate)
        .join(TollSection, TollGate.section_id == TollSection.id)
        .where(TollGate.is_active.is_(True))
        .where(TollSection.is_active.is_(True))
        .options(selectinload(TollGate.section))
        .order_by(TollGate.section_id.asc(), TollGate.sort_order.asc(), TollGate.id.asc())
    ).all()
    fare_rows = db.execute(
        select(TollGateFare, TollGolongan.code)
        .join(TollGolongan, TollGateFare.golongan_id == TollGolongan.id)
        .join(TollGate, TollGateFare.entry_gate_id == TollGate.id)
        .join(TollSection, TollGate.section_id == TollSection.id)
        .where(TollGate.is_active.is_(True))
        .where(TollSection.is_active.is_(True))
    ).all()
    return serialize_gate_fare_context(gates, fare_rows)


def _toll_gate_out(obj: TollGate) -> TollGateOut:
    return TollGateOut(
        id=obj.id,
        section_id=obj.section_id,
        section_name=obj.section.name if obj.section else None,
        code=obj.code,
        name=obj.name,
        latitude=float(obj.latitude) if obj.latitude is not None else None,
        longitude=float(obj.longitude) if obj.longitude is not None else None,
        sort_order=obj.sort_order,
        is_active=obj.is_active,
    )


def _toll_gate_fare_out(db: Session, obj: TollGateFare) -> TollGateFareOut:
    entry = db.get(TollGate, obj.entry_gate_id)
    exit_gate = db.get(TollGate, obj.exit_gate_id)
    gol = obj.golongan or db.get(TollGolongan, obj.golongan_id)
    section_id = entry.section_id if entry else 0
    section_name = entry.section.name if entry and entry.section else None
    return TollGateFareOut(
        id=obj.id,
        section_id=section_id,
        section_name=section_name,
        entry_gate_id=obj.entry_gate_id,
        entry_gate_code=entry.code if entry else "-",
        entry_gate_name=entry.name if entry else "-",
        exit_gate_id=obj.exit_gate_id,
        exit_gate_code=exit_gate.code if exit_gate else "-",
        exit_gate_name=exit_gate.name if exit_gate else "-",
        golongan_id=obj.golongan_id,
        golongan_code=gol.code if gol else "?",
        golongan_name=gol.name if gol else "-",
        rate=float(obj.rate),
    )


def _validate_gate_fare(db: Session, entry_gate_id: int, exit_gate_id: int, golongan_id: int) -> tuple[TollGate, TollGate]:
    if entry_gate_id == exit_gate_id:
        raise HTTPException(status_code=400, detail="Gerbang masuk dan keluar tidak boleh sama.")
    entry = db.get(TollGate, entry_gate_id)
    exit_gate = db.get(TollGate, exit_gate_id)
    if not entry or not exit_gate:
        raise HTTPException(status_code=400, detail="Gerbang tol tidak ditemukan.")
    if entry.section_id != exit_gate.section_id:
        raise HTTPException(status_code=400, detail="Gerbang masuk dan keluar harus pada ruas tol yang sama.")
    if not db.get(TollGolongan, golongan_id):
        raise HTTPException(status_code=400, detail="Golongan tol tidak ditemukan.")
    return entry, exit_gate


def _vehicle_type_out(obj: VehicleType) -> VehicleTypeOut:
    gol = obj.toll_golongan
    bbm = obj.bbm
    uang_mel = obj.uang_mel
    return VehicleTypeOut(
        id=obj.id,
        name=obj.name,
        toll_golongan_id=obj.toll_golongan_id,
        toll_golongan_name=gol.name if gol else None,
        toll_golongan_code=gol.code if gol else None,
        bbm_id=obj.bbm_id,
        bbm_name=bbm.name if bbm else None,
        bbm_price=float(bbm.price) if bbm else None,
        uang_mel_id=obj.uang_mel_id,
        uang_mel_name=uang_mel.name if uang_mel else None,
        uang_mel_amount=float(uang_mel.amount) if uang_mel else 0,
        km_per_liter=float(obj.km_per_liter) if obj.km_per_liter is not None else None,
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


def _validate_uang_mel_id(db: Session, uang_mel_id: int | None) -> None:
    if uang_mel_id is None:
        return
    if not db.get(UangMelMaster, uang_mel_id):
        raise HTTPException(status_code=400, detail="Master Uang Mel tidak ditemukan")


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
        is_locked_marketing=customer.is_locked_marketing,
        is_locked_finance=customer.is_locked_finance,
        updated_at=customer.updated_at,
        updated_by_name=customer.updated_by_user.full_name if customer.updated_by_user else None,
        custom_toll_breakdown=json.loads(customer.custom_toll_breakdown) if customer.custom_toll_breakdown else None,
        latitude=float(customer.latitude) if customer.latitude is not None else None,
        longitude=float(customer.longitude) if customer.longitude is not None else None,
        share_location=customer.share_location,
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
        is_locked_marketing=customer.is_locked_marketing,
        is_locked_finance=customer.is_locked_finance,
        updated_at=customer.updated_at,
        updated_by_name=customer.updated_by_user.full_name if customer.updated_by_user else None,
    )


@router.get("/customers", response_model=list[CustomerListOut])
def list_customers(db: Session = Depends(get_db)):
    customers = db.scalars(
        select(Customer)
        .options(selectinload(Customer.updated_by_user))
        .order_by(nulls_last(Customer.code.asc()), Customer.name.asc())
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
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), current_user: User = Depends(require_api_access)):
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
        is_locked_marketing=payload.is_locked_marketing,
        is_locked_finance=payload.is_locked_finance,
        updated_at=func.now(),
        updated_by_id=current_user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        share_location=payload.share_location,
        custom_toll_breakdown=json.dumps(payload.custom_toll_breakdown) if payload.custom_toll_breakdown else None,
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
def update_customer(customer_id: int, payload: CustomerCreate, db: Session = Depends(get_db), current_user: User = Depends(require_api_access)):
    # Use with_for_update() to lock the customer row and prevent DELETE/INSERT race conditions
    # on tariffs if there are concurrent update requests.
    obj = db.execute(select(Customer).where(Customer.id == customer_id).with_for_update()).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Check if finance can unlock customers
    app_setting = db.scalars(select(AppSetting).limit(1)).first()
    finance_can_unlock = app_setting.finance_can_unlock_customer if app_setting else False

    if obj.is_locked_finance and current_user.role != "admin":
        if current_user.role == "finance" and finance_can_unlock:
            pass  # Finance is allowed to unlock
        else:
            raise HTTPException(status_code=403, detail="Customer telah dikunci final (Finance) dan hanya dapat diubah oleh Admin")
    
    if current_user.role == "marketing":
        if obj.is_locked_marketing and payload.is_locked_marketing:
            raise HTTPException(status_code=403, detail="Customer telah dikunci. Hilangkan centang Kunci Marketing terlebih dahulu untuk menyimpan perubahan.")
    
    if payload.is_locked_finance and not payload.is_locked_marketing:
        raise HTTPException(status_code=400, detail="Kunci Finance hanya dapat dilakukan jika Kunci Marketing sudah aktif.")

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

    if current_user.role == "marketing":
        obj.is_locked_marketing = payload.is_locked_marketing
        # Ignore attempts to change finance lock
    else:
        obj.is_locked_marketing = payload.is_locked_marketing
        obj.is_locked_finance = payload.is_locked_finance

    obj.updated_at = func.now()
    obj.updated_by_id = current_user.id
    obj.latitude = payload.latitude
    obj.longitude = payload.longitude
    obj.share_location = payload.share_location
    obj.custom_toll_breakdown = json.dumps(payload.custom_toll_breakdown) if payload.custom_toll_breakdown else None

    try:
        _replace_customer_tariffs(db, obj.id, payload.tariffs)
        refresh_customer_tariff_in_sales(db, obj.id)
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


@router.get("/uang-mel", response_model=list[UangMelOut])
def list_uang_mel(db: Session = Depends(get_db)):
    return db.scalars(select(UangMelMaster).order_by(UangMelMaster.name.asc())).all()


@router.post("/uang-mel", response_model=UangMelOut, status_code=201)
def create_uang_mel(payload: UangMelCreate, db: Session = Depends(get_db)):
    obj = UangMelMaster(name=payload.name.strip(), amount=payload.amount)
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.put("/uang-mel/{mel_id}", response_model=UangMelOut)
def update_uang_mel(mel_id: int, payload: UangMelCreate, db: Session = Depends(get_db)):
    obj = db.get(UangMelMaster, mel_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Master Uang Mel tidak ditemukan")
    obj.name = payload.name.strip()
    obj.amount = payload.amount
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.delete("/uang-mel/{mel_id}", status_code=204)
def delete_uang_mel(mel_id: int, db: Session = Depends(get_db)):
    obj = db.get(UangMelMaster, mel_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Master Uang Mel tidak ditemukan")
    in_use = db.scalar(
        select(func.count()).select_from(VehicleType).where(VehicleType.uang_mel_id == mel_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Uang Mel masih dipakai jenis kendaraan. Ubah jenis kendaraan tersebut dulu.",
        )
    db.delete(obj)
    db.commit()


def _load_vehicle_types_query():
    return (
        select(VehicleType)
        .options(
            selectinload(VehicleType.toll_golongan),
            selectinload(VehicleType.bbm),
            selectinload(VehicleType.uang_mel),
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
    _validate_uang_mel_id(db, payload.uang_mel_id)
    obj = VehicleType(
        name=payload.name.strip(),
        toll_golongan_id=payload.toll_golongan_id,
        bbm_id=payload.bbm_id,
        uang_mel_id=payload.uang_mel_id,
        km_per_liter=payload.km_per_liter,
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
    _validate_uang_mel_id(db, payload.uang_mel_id)
    obj.name = payload.name.strip()
    obj.toll_golongan_id = payload.toll_golongan_id
    obj.bbm_id = payload.bbm_id
    obj.uang_mel_id = payload.uang_mel_id
    obj.km_per_liter = payload.km_per_liter
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
    finance_status: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Sale)
        .options(selectinload(Sale.details))
        .where(Sale.is_void == False)
        .where(Sale.driver_id.isnot(None))
        .where(Sale.vehicle_id.isnot(None))
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
    if finance_status == "paid":
        stmt = stmt.where(Sale.finance_paid_at.isnot(None))
    elif finance_status == "pending":
        stmt = stmt.where(Sale.finance_paid_at.is_(None))

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
                customer_is_locked=bool(cust.is_locked_finance) if cust else False,
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
        is_void=obj.is_void,
        void_reason=obj.void_reason,
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
        missing_tariff_customers=customers_missing_tariff(db, route),
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
    if payload.vehicle_id is not None and not db.get(Vehicle, payload.vehicle_id):
        raise HTTPException(status_code=400, detail="Kendaraan tidak ditemukan")
    if payload.driver_id is not None and not db.get(Driver, payload.driver_id):
        raise HTTPException(status_code=400, detail="Sopir tidak ditemukan")
    
    # Generate sale_no if not provided
    sale_no = payload.sale_no
    if not sale_no:
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
        sale_no = f"{prefix}{counter:04d}"
    
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
    if getattr(obj, "is_void", False):
        raise HTTPException(status_code=400, detail="Transaksi sudah berstatus void dan tidak dapat disetujui.")
    if sale_finance_locked(obj):
        raise HTTPException(status_code=400, detail="Pembayaran uang jalan sudah disetujui.")
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


@router.post("/sales/{sale_id}/void", response_model=SaleOut)
def void_sale(
    sale_id: int,
    payload: SaleVoid,
    user: User = Depends(require_permission("sales:write")),
    db: Session = Depends(get_db),
):
    if user.role not in (Role.GUDANG.value, Role.ADMIN.value):
        raise HTTPException(
            status_code=403,
            detail="Hanya Gudang atau Admin yang dapat melakukan void transaksi.",
        )
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")
    if getattr(obj, "is_void", False):
        raise HTTPException(status_code=400, detail="Transaksi sudah berstatus void.")
    if sale_finance_locked(obj):
        raise HTTPException(status_code=400, detail="Uang jalan sudah disetujui finance dan tidak bisa divoid.")
    
    obj.is_void = True
    obj.void_reason = payload.void_reason
    db.commit()
    db.refresh(obj)
    return _serialize_sale(db, obj)


@router.put("/sales/{sale_id}", response_model=SaleOut)
def update_sale(sale_id: int, payload: SaleCreate, db: Session = Depends(get_db)):
    db.execute(select(Sale).where(Sale.id == sale_id).with_for_update()).scalar_one_or_none()
    obj = db.get(Sale, sale_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Penjualan tidak ditemukan")
    if getattr(obj, "is_void", False):
        raise HTTPException(status_code=400, detail="Transaksi sudah berstatus void dan tidak dapat diedit.")

    from app.sale_lock import sale_finance_locked
    if sale_finance_locked(obj):
        if payload.vehicle_id is not None and not db.get(Vehicle, payload.vehicle_id):
            raise HTTPException(status_code=400, detail="Kendaraan tidak ditemukan")
        if payload.driver_id is not None and not db.get(Driver, payload.driver_id):
            raise HTTPException(status_code=400, detail="Sopir tidak ditemukan")
        obj.vehicle_id = payload.vehicle_id
        obj.driver_id = payload.driver_id
        try:
            db.commit()
            db.refresh(obj)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Gagal mengupdate transaksi: {e}")
        return _serialize_sale(db, obj)
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
        if payload.vehicle_id is not None and not db.get(Vehicle, payload.vehicle_id):
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

    if payload.vehicle_id is not None and not db.get(Vehicle, payload.vehicle_id):
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
        now = datetime.now()
        prefix = now.strftime("RT%y%m")
        last_route = db.scalar(
            select(DeliveryRoute.route_no)
            .where(DeliveryRoute.route_no.like(f"{prefix}%"))
            .order_by(DeliveryRoute.route_no.desc())
            .limit(1)
        )
        if last_route and len(last_route) == 10:
            try:
                counter = int(last_route[6:]) + 1
            except ValueError:
                counter = 1
        else:
            counter = 1
        route_no = f"{prefix}{counter:04d}"

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
    obj.custom_toll_breakdown = None
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
    gate_context = _load_toll_gate_fare_context(db)
    route = calculate_route(
        origin_lat,
        origin_lng,
        dest_lat,
        dest_lng,
        sections=sections,
        force_toll=payload.force_toll,
        gate_context=gate_context,
        prefer_cheapest_toll=payload.prefer_cheapest_toll is not False,
    )

    is_custom_breakdown = False
    if customer is not None and customer.custom_toll_breakdown:
        if (customer.latitude and dest_lat == float(customer.latitude) and
            customer.longitude and dest_lng == float(customer.longitude) and
            payload.force_toll == customer.force_toll):
            custom_segments = json.loads(customer.custom_toll_breakdown)
            if custom_segments:
                route["toll_breakdown"] = custom_segments
                route["toll_source"] = "manual"
                route["toll_is_estimate"] = False
                is_custom_breakdown = True

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
    
    if is_custom_breakdown:
        custom_segments = route["toll_breakdown"]
        toll_by_vehicle_raw = []
        for vt in vehicle_types:
            gol_code = vt.toll_golongan.code if vt.toll_golongan else "II"
            meta = VEHICLE_TOLL_CLASS.get(_match_toll_vehicle_key(vt.name) or "", {})
            total_one_way = 0.0
            for seg in custom_segments:
                rates = seg.get("rates_by_golongan") or {}
                val = rates.get(gol_code)
                if val is None:
                    if gol_code == "III": val = rates.get("II")
                    elif gol_code == "V": val = rates.get("IV")
                    if val is None:
                        val = rates.get("II", rates.get("III", rates.get("IV", 0)))
                total_one_way += float(val or 0)
            toll = round(total_one_way * 2, 0)
            if toll > 0:
                toll = float(((int(toll) + 999) // 1000) * 1000)
            rate_per_km = round(toll / route["distance_km"], 0) if route.get("distance_km") else 0.0
            toll_by_vehicle_raw.append({
                "vehicle_type_id": vt.id,
                "vehicle_type_name": vt.name,
                "golongan": gol_code,
                "gandar": meta.get("gandar", "-") if isinstance(meta, dict) else "-",
                "toll_idr": toll,
                "rate_per_km": rate_per_km,
            })
        toll_by_vehicle_raw.sort(key=lambda item: item["vehicle_type_name"].lower())
    elif gate_context.get("fares") and not route["toll_is_estimate"]:
        toll_by_vehicle_raw = []
        for vt in vehicle_types:
            gol_code = vt.toll_golongan.code if vt.toll_golongan else "II"
            meta = VEHICLE_TOLL_CLASS.get(
                _match_toll_vehicle_key(vt.name) or "", {}
            )
            bpjt = estimate_toll_bpjt_gates(
                origin_lat,
                origin_lng,
                dest_lat,
                dest_lng,
                gate_context["gates"],
                gate_context["fares"],
                gol_code,
                distance_km=route["distance_km"],
                route_toll_roads=route.get("toll_roads") or [],
                sections=sections,
            )
            toll = round(bpjt[0] * 2, 0) if bpjt else route["toll_idr"]
            if toll > 0:
                toll = float(((int(toll) + 999) // 1000) * 1000)
            rate_per_km = round(toll / route["distance_km"], 0) if route["distance_km"] else 0.0
            toll_by_vehicle_raw.append(
                {
                    "vehicle_type_id": vt.id,
                    "vehicle_type_name": vt.name,
                    "golongan": gol_code,
                    "gandar": meta.get("gandar", "-") if isinstance(meta, dict) else "-",
                    "toll_idr": toll,
                    "rate_per_km": rate_per_km,
                }
            )
        toll_by_vehicle_raw.sort(key=lambda item: item["vehicle_type_name"].lower())
    else:
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


@router.post("/routing/toll-breakdown/manual", response_model=ManualTollBreakdownOut)
def manual_toll_breakdown(payload: ManualTollBreakdownRequest, db: Session = Depends(get_db)):
    sections = _load_active_toll_sections(db)
    gate_context = _load_toll_gate_fare_context(db)
    result = build_manual_toll_breakdown(
        payload.section_ids,
        sections,
        gate_context.get("gates") or [],
        gate_context.get("fares") or [],
        golongan_code="II",
    )
    return ManualTollBreakdownOut(**result)


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
    in_use_rates = db.scalar(
        select(exists().where(TollSectionRate.golongan_id == golongan_id))
    )
    in_use_fares = db.scalar(
        select(exists().where(TollGateFare.golongan_id == golongan_id))
    )
    if in_use_rates or in_use_fares:
        raise HTTPException(
            status_code=400,
            detail="Golongan masih dipakai di ruas tol atau tarif gerbang.",
        )
    db.delete(obj)
    db.commit()


@router.get("/toll-sections", response_model=list[TollSectionOut])
def list_toll_sections(db: Session = Depends(get_db)):
    rows = db.scalars(_load_toll_sections_query()).all()
    return [_toll_section_out(row) for row in rows]


@router.get("/toll-sections/{section_id}", response_model=TollSectionOut)
def get_toll_section(section_id: int, db: Session = Depends(get_db)):
    row = db.scalars(_load_toll_sections_query().filter(TollSection.id == section_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Ruas tol tidak ditemukan.")
    return _toll_section_out(row)


@router.post("/toll-sections", response_model=TollSectionOut, status_code=201)
def create_toll_section(payload: TollSectionCreate, db: Session = Depends(get_db)):
    obj = TollSection(
        network=payload.network.strip() if payload.network else None,
        name=payload.name.strip(),
        origin_name=payload.origin_name.strip() if payload.origin_name else None,
        destination_name=payload.destination_name.strip() if payload.destination_name else None,
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
    if "network" in data:
        data["network"] = data["network"].strip() if data["network"] else None
    if "origin_name" in data:
        data["origin_name"] = data["origin_name"].strip() if data["origin_name"] else None
    if "destination_name" in data:
        data["destination_name"] = data["destination_name"].strip() if data["destination_name"] else None
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


@router.post("/toll-sections/sync-bpjt-jabodetabek", response_model=BpjtFullImportResultOut)
def sync_bpjt_jabodetabek_tolls(db: Session = Depends(get_db)):
    """Impor ruas tol + matriks gerbang Jabodetabek dari dataset resmi BPJT."""
    try:
        result = import_jabodetabek_all(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal impor BPJT: {exc}") from exc
    return BpjtFullImportResultOut(
        sections=BpjtImportResultOut(**result["sections"]),
        gates=BpjtGateImportResultOut(**result["gates"]),
    )


@router.post("/toll-gates/sync-bpjt-jabodetabek", response_model=BpjtGateImportResultOut)
def sync_bpjt_jabodetabek_gates(db: Session = Depends(get_db)):
    """Impor matriks gerbang Jabodetabek saja (ruas harus sudah diimpor)."""
    try:
        result = import_jabodetabek_gate_matrices(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal impor gerbang BPJT: {exc}") from exc
    return BpjtGateImportResultOut(**result)


@router.post("/toll-gates/refresh-coordinates", response_model=TollGateCoordRefreshResultOut)
def refresh_toll_gate_coordinates(db: Session = Depends(get_db)):
    """Perbarui koordinat semua gerbang dari data OSM yang dibundel."""
    try:
        result = refresh_gate_coordinates(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui koordinat gerbang: {exc}") from exc
    return TollGateCoordRefreshResultOut(**result)


@router.get("/toll-gates", response_model=list[TollGateOut])
def list_toll_gates(
    section_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(TollGate)
        .options(selectinload(TollGate.section))
        .order_by(TollGate.section_id.asc(), TollGate.sort_order.asc(), TollGate.id.asc())
    )
    if section_id:
        stmt = stmt.where(TollGate.section_id == section_id)
    rows = db.scalars(stmt).all()
    return [_toll_gate_out(row) for row in rows]


@router.post("/toll-gates", response_model=TollGateOut, status_code=201)
def create_toll_gate(payload: TollGateCreate, db: Session = Depends(get_db)):
    if not db.get(TollSection, payload.section_id):
        raise HTTPException(status_code=404, detail="Ruas tol tidak ditemukan")
    obj = TollGate(
        section_id=payload.section_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
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
    obj = db.scalar(
        select(TollGate).where(TollGate.id == obj.id).options(selectinload(TollGate.section))
    )
    return _toll_gate_out(obj)


@router.put("/toll-gates/{gate_id}", response_model=TollGateOut)
def update_toll_gate(gate_id: int, payload: TollGateUpdate, db: Session = Depends(get_db)):
    obj = db.get(TollGate, gate_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Gerbang tol tidak ditemukan")
    data = payload.model_dump(exclude_unset=True)
    if "section_id" in data and data["section_id"] is not None:
        if not db.get(TollSection, data["section_id"]):
            raise HTTPException(status_code=404, detail="Ruas tol tidak ditemukan")
    if "code" in data and data["code"] is not None:
        data["code"] = data["code"].strip().upper()
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(obj, key, value)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    obj = db.scalar(
        select(TollGate).where(TollGate.id == obj.id).options(selectinload(TollGate.section))
    )
    return _toll_gate_out(obj)


@router.delete("/toll-gates/{gate_id}", status_code=204)
def delete_toll_gate(gate_id: int, db: Session = Depends(get_db)):
    obj = db.get(TollGate, gate_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Gerbang tol tidak ditemukan")
    db.delete(obj)
    db.commit()


@router.get("/toll-gate-fares", response_model=list[TollGateFareOut])
def list_toll_gate_fares(
    section_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(TollGateFare)
        .join(TollGate, TollGateFare.entry_gate_id == TollGate.id)
        .options(
            selectinload(TollGateFare.entry_gate).selectinload(TollGate.section),
            selectinload(TollGateFare.exit_gate),
            selectinload(TollGateFare.golongan),
        )
        .order_by(TollGate.section_id.asc(), TollGateFare.id.asc())
    )
    if section_id:
        stmt = stmt.where(TollGate.section_id == section_id)
    rows = db.scalars(stmt).all()
    return [_toll_gate_fare_out(db, row) for row in rows]


@router.post("/toll-gate-fares", response_model=TollGateFareOut, status_code=201)
def create_toll_gate_fare(payload: TollGateFareCreate, db: Session = Depends(get_db)):
    _validate_gate_fare(db, payload.entry_gate_id, payload.exit_gate_id, payload.golongan_id)
    obj = TollGateFare(
        entry_gate_id=payload.entry_gate_id,
        exit_gate_id=payload.exit_gate_id,
        golongan_id=payload.golongan_id,
        rate=payload.rate,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return _toll_gate_fare_out(db, obj)


@router.put("/toll-gate-fares/{fare_id}", response_model=TollGateFareOut)
def update_toll_gate_fare(
    fare_id: int, payload: TollGateFareUpdate, db: Session = Depends(get_db)
):
    obj = db.get(TollGateFare, fare_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Tarif gerbang tidak ditemukan")
    data = payload.model_dump(exclude_unset=True)
    entry_id = data.get("entry_gate_id", obj.entry_gate_id)
    exit_id = data.get("exit_gate_id", obj.exit_gate_id)
    gol_id = data.get("golongan_id", obj.golongan_id)
    _validate_gate_fare(db, entry_id, exit_id, gol_id)
    for key, value in data.items():
        setattr(obj, key, value)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return _toll_gate_fare_out(db, obj)


@router.delete("/toll-gate-fares/{fare_id}", status_code=204)
def delete_toll_gate_fare(fare_id: int, db: Session = Depends(get_db)):
    obj = db.get(TollGateFare, fare_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Tarif gerbang tidak ditemukan")
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
        note=TOLL_NOTE_BPJT,
    )


@router.post("/geocode", response_model=GeocodeOut)
def geocode_point(payload: GeocodeRequest):
    lat, lng = geocode_address(payload.address, payload.kelurahan, payload.kecamatan, payload.city, payload.name)
    return GeocodeOut(latitude=lat, longitude=lng)


@router.post("/geocode/from-share", response_model=GeocodeOut)
def geocode_from_share(payload: GeocodeFromShareRequest):
    lat, lng = parse_coords_from_share(payload.text)
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
    if "finance_can_unlock_customer" in update_data and update_data["finance_can_unlock_customer"] is not None:
        setting.finance_can_unlock_customer = update_data["finance_can_unlock_customer"]

    db.commit()
    db.refresh(setting)
    return setting


@router.get("/toll-data/export", response_model=TollDataExport, dependencies=[Depends(require_permission("toll:write"))])
def export_toll_data(db: Session = Depends(get_db)):
    golongan = db.execute(select(TollGolongan)).scalars().all()
    sections = db.execute(select(TollSection)).scalars().all()
    section_rates = db.execute(select(TollSectionRate)).scalars().all()
    gates = db.execute(select(TollGate)).scalars().all()
    gate_fares = db.execute(select(TollGateFare)).scalars().all()
    
    return TollDataExport(
        golongan=[{
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "description": g.description,
            "sort_order": g.sort_order,
            "is_active": g.is_active,
        } for g in golongan],
        sections=[{
            "id": s.id,
            "network": s.network,
            "name": s.name,
            "origin_name": s.origin_name,
            "destination_name": s.destination_name,
            "length_km": float(s.length_km),
            "gol23": float(s.gol23),
            "gol45": float(s.gol45),
            "sort_order": s.sort_order,
            "is_active": s.is_active,
        } for s in sections],
        section_rates=[{
            "section_id": r.section_id,
            "golongan_id": r.golongan_id,
            "rate": float(r.rate),
        } for r in section_rates],
        gates=[{
            "id": g.id,
            "section_id": g.section_id,
            "code": g.code,
            "name": g.name,
            "latitude": float(g.latitude) if g.latitude else None,
            "longitude": float(g.longitude) if g.longitude else None,
            "sort_order": g.sort_order,
            "is_active": g.is_active,
        } for g in gates],
        gate_fares=[{
            "entry_gate_id": f.entry_gate_id,
            "exit_gate_id": f.exit_gate_id,
            "golongan_id": f.golongan_id,
            "rate": float(f.rate),
        } for f in gate_fares],
    )

@router.post("/toll-data/import", dependencies=[Depends(require_permission("toll:write"))])
def import_toll_data(payload: TollDataExport, db: Session = Depends(get_db)):
    try:
        # Upsert TollGolongan
        existing_gol = {g.id: g for g in db.execute(select(TollGolongan)).scalars().all()}
        for g in payload.golongan:
            if g.id in existing_gol:
                obj = existing_gol[g.id]
                obj.name = g.name
                obj.code = g.code
                obj.description = g.description
                obj.sort_order = g.sort_order
                obj.is_active = g.is_active
            else:
                db.add(TollGolongan(**g.model_dump()))
        
        db.flush()

        # Wipe and Replace TollSections and Gates
        db.execute(delete(TollSection))
        db.execute(delete(TollGate))
        db.flush()

        for s in payload.sections:
            db.add(TollSection(**s.model_dump()))
        db.flush()
        
        for r in payload.section_rates:
            db.add(TollSectionRate(**r.model_dump()))
            
        for g in payload.gates:
            db.add(TollGate(**g.model_dump()))
        db.flush()
        
        for f in payload.gate_fares:
            db.add(TollGateFare(**f.model_dump()))
            
        db.commit()
        
        # Reset sequences
        from app.db_tools import _reset_all_sequences
        with db.connection() as conn:
            _reset_all_sequences(conn)
            db.commit()
            
        return {"detail": "Import berhasil"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Gagal import data: {str(e)}")

