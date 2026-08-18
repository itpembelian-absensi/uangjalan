from __future__ import annotations

import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, exists, func, nulls_last, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.auth import require_api_access, require_permission
from app.sale_lock import (
    MSG_ROUTE_FINANCE_PAID,
    assert_route_editable,
    assert_sale_editable,
    route_sale,
    sale_finance_locked,
)
from app.permissions_service import (
    CUSTOMER_FINANCE_LOCK_PERMISSION,
    has_permission,
)
from app.roles import Role
from app.db import get_db
from app.money_utils import compute_uang_jalan_totals
from app.pelabuhan_service import resolve_uang_pelabuhan
from app.route_fee_service import (
    ROUTE_FEE_DEFS,
    apply_route_fees_from_payload,
    get_route_fee_def,
    sum_route_fees,
)
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
    UangPelabuhanMaster,
    RouteFeeMaster,
)
from app.toll_gate_service import (
    TOLL_NOTE_BPJT,
    build_manual_toll_breakdown,
    estimate_toll_bpjt_gates,
    refresh_gate_coordinates,
    serialize_gate_fare_context,
    waypoints_from_toll_segments,
)
from app.route_profiles import (
    list_route_profiles,
    profile_adaptation_note,
    resolve_effective_profile_key,
    resolve_profile_section_ids,
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
    customer_tariff_report,
    delivery_route_report,
    disbursement_detail,
    driver_summary,
)
from app.routing_service import (
    VEHICLE_TOLL_CLASS,
    _match_toll_vehicle_key,
    _driving_distance,
    build_toll_road_overlays,
    calculate_route,
    calculate_route_chained,
    collapse_sections_for_routing,
    estimate_tolls_by_vehicle,
    geocode_address,
    parse_coords_from_share,
    get_toll_reference,
    serialize_toll_sections,
    vehicle_toll_allowed,
    _default_sections_from_settings,
)
from app.schemas import (
    CashDisbursementCreate,
    CashDisbursementOut,
    CustomerCreate,
    CustomerOut,
    CustomerListOut,
    CustomerBulkImport,
    CustomerUnlockAllOut,
    CustomerLockAllOut,
    CustomerLockRestoreStatusOut,
    CustomerRelockPreviousOut,
    CustomerSummaryRow,
    CustomerTariffReportRow,
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
    UangPelabuhanCreate,
    UangPelabuhanOut,
    RouteFeeCreate,
    RouteFeeOut,
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
    RouteProfileOut,
    ManualTollBreakdownRequest,
    ManualTollBreakdownOut,
    RouteRecalculateRequest,
    RouteRecalculateOut,
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


def _load_active_toll_sections(db: Session, *, collapse: bool = True) -> list[dict]:
    """
    Muat master ruas tol aktif.

    collapse=True  → gabungkan exit-variant (nama sama) jadi 1 acuan (deteksi rute otomatis).
    collapse=False → semua baris tetap (wajib untuk pilih manual Karawaci/Cikupa/dll).
    """
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
    serialized = serialize_toll_sections(rows)
    if collapse:
        return collapse_sections_for_routing(serialized)
    return serialized


def _toll_by_vehicle_from_manual_segments(
    custom_segments: list[dict],
    vehicle_types,
    distance_km: float,
) -> list[dict]:
    toll_by_vehicle_raw = []
    for vt in vehicle_types:
        gol_code = vt.toll_golongan.code if vt.toll_golongan else "II"
        meta = VEHICLE_TOLL_CLASS.get(_match_toll_vehicle_key(vt.name) or "", {})
        total_one_way = 0.0
        if vehicle_toll_allowed(vt.name):
            for seg in custom_segments:
                rates = seg.get("rates_by_golongan") or {}
                val = rates.get(gol_code)
                if val is None:
                    if gol_code == "III":
                        val = rates.get("II")
                    elif gol_code == "V":
                        val = rates.get("IV")
                    if val is None:
                        val = rates.get("II", rates.get("III", rates.get("IV", 0)))
                total_one_way += float(val or 0)
        toll = round(total_one_way * 2, 0)
        if toll > 0:
            toll = float(((int(toll) + 999) // 1000) * 1000)
        rate_per_km = round(toll / distance_km, 0) if distance_km else 0.0
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
    return toll_by_vehicle_raw


def _resolve_route_section_ids(
    payload: RouteProcessRequest,
    customer: Customer | None,
    sections: list[dict],
    dest_lat: float,
    dest_lng: float,
) -> tuple[list[int], str]:
    if payload.section_ids:
        return [int(sid) for sid in payload.section_ids], "manual"

    profile_key = (payload.route_profile or "auto").strip().lower()
    if profile_key not in ("auto", "manual", ""):
        effective = resolve_effective_profile_key(profile_key, dest_lat, dest_lng)
        ids = resolve_profile_section_ids(profile_key, sections, dest_lat, dest_lng)
        return ids, effective

    if profile_key == "manual":
        if payload.section_ids:
            return [int(sid) for sid in payload.section_ids], profile_key
        if customer is not None and customer.custom_toll_breakdown:
            try:
                segments = json.loads(customer.custom_toll_breakdown)
                ids = [int(s["section_id"]) for s in segments if s.get("section_id")]
                if ids:
                    return ids, profile_key
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return [], profile_key


def _build_corridor_route(
    *,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    section_ids: list[int],
    sections: list[dict],
    gate_context: dict,
    force_toll: bool,
    vehicle_types,
    note_prefix: str | None = None,
    distance_provider: str = "osrm",
) -> tuple[dict, list[dict]]:
    gates = gate_context.get("gates") or []
    manual = build_manual_toll_breakdown(
        section_ids,
        sections,
        gates,
        gate_context.get("fares") or [],
        golongan_code="II",
    )
    custom_segments = manual["segments"]
    waypoints = waypoints_from_toll_segments(
        custom_segments,
        gates,
        origin_lat,
        origin_lng,
        dest_lat,
        dest_lng,
        sections=sections,
    )
    route_via_toll_gates = len(waypoints) > 0
    corridor_used = False

    if route_via_toll_gates:
        route, corridor_used = calculate_route_chained(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            waypoints,
            sections=sections,
            force_toll=force_toll,
            gate_context=gate_context,
            prefer_corridor=True,
        )
    else:
        route = calculate_route(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            sections=sections,
            force_toll=force_toll,
            gate_context=gate_context,
            prefer_cheapest_toll=False,
            waypoints=None,
            distance_provider="osrm",
        )

    toll_note = manual.get("toll_note") or (
        "Tarif ruas tol dipilih manual dari master BPJT. Total pulang-pergi dikali 2."
    )
    if note_prefix:
        toll_note = f"{note_prefix} {toll_note}"
    if route_via_toll_gates and corridor_used:
        toll_note = f"Jarak & peta mengikuti koridor gerbang tol (OSRM). {toll_note}"
    elif route_via_toll_gates and not corridor_used:
        route_via_toll_gates = False
        toll_note = (
            "Koridor gerbang gagal dihitung — jarak & peta memakai rute OSRM langsung. "
            + toll_note
        )
    else:
        toll_note = (
            "Koordinat gerbang tol belum lengkap — jarak & peta dari rute OSRM langsung. "
            + toll_note
        )

    provider = (distance_provider or "osrm").strip().lower()
    route_km = float(route.get("distance_km") or 0)
    route_dur = float(route.get("duration_min") or 0)
    route["distance_km_route"] = route_km
    route["duration_min_route"] = route_dur

    # Selalu sediakan jarak langsung (≈ Google) untuk perbandingan di UI
    try:
        direct = _driving_distance(
            origin_lat, origin_lng, dest_lat, dest_lng, provider="osrm_direct"
        )
        route["distance_km_direct"] = float(direct["distance_km"])
        route["duration_min_direct"] = float(direct["duration_min"] or 0)
    except Exception:
        route["distance_km_direct"] = route_km
        route["duration_min_direct"] = route_dur

    if provider in ("google", "osrm_direct", "direct"):
        # Jarak BBM diganti; peta/koridor tetap OSRM visual
        driving = _driving_distance(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            provider="google" if provider == "google" else "osrm_direct",
        )
        route["distance_km"] = driving["distance_km"]
        route["duration_min"] = driving["duration_min"]
        route["distance_source"] = driving["source"]
        if driving["source"] == "google":
            route["distance_km_direct"] = float(driving["distance_km"])
            route["duration_min_direct"] = float(driving["duration_min"] or 0)
            toll_note = (
                f"Jarak BBM dari Google Maps ({driving['distance_km']} km). " + toll_note
            )
        else:
            toll_note = (
                f"Jarak BBM dari OSRM langsung ({driving['distance_km']} km), "
                f"mendekati Google Maps. " + toll_note
            )
    else:
        route["distance_source"] = "osrm"
        route["distance_km"] = route_km
        route["duration_min"] = route_dur

    toll_by_vehicle_raw = _toll_by_vehicle_from_manual_segments(
        custom_segments,
        vehicle_types,
        route["distance_km"],
    )
    toll_idr = toll_by_vehicle_raw[0]["toll_idr"] if toll_by_vehicle_raw else manual["toll_idr"]

    route["toll_breakdown"] = custom_segments
    route["toll_idr"] = toll_idr
    route["toll_is_estimate"] = False
    route["toll_note"] = toll_note
    route["toll_source"] = "manual"
    route["route_via_toll_gates"] = route_via_toll_gates
    route["route_selection"] = None
    route["alternatives_compared"] = 0
    route["toll_savings_idr"] = None
    # Garis oranye mengikuti jalur jalan (OSRM), bukan lurus gerbang→gerbang
    route["toll_roads"] = build_toll_road_overlays(custom_segments, gates)
    return route, toll_by_vehicle_raw


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


def _vehicle_type_out(obj: VehicleType, db: Session) -> VehicleTypeOut:
    gol = obj.toll_golongan
    bbm = obj.bbm
    uang_mel = obj.uang_mel
    pelabuhan_name, pelabuhan_amount = resolve_uang_pelabuhan(db, obj)
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
        uang_pelabuhan_id=obj.uang_pelabuhan_id,
        uang_pelabuhan_name=pelabuhan_name,
        uang_pelabuhan_amount=pelabuhan_amount,
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


def _validate_uang_pelabuhan_id(db: Session, uang_pelabuhan_id: int | None) -> None:
    if uang_pelabuhan_id is None:
        return
    if not db.get(UangPelabuhanMaster, uang_pelabuhan_id):
        raise HTTPException(status_code=400, detail="Master Uang Pelabuhan tidak ditemukan")


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
        vehicle_type = db.get(VehicleType, row.vehicle_type_id)
        toll = row.tol if vehicle_type and vehicle_toll_allowed(vehicle_type.name) else 0
        component_total = row.bbm + toll + row.uang_mel + row.parkir + row.lain_lain
        total = component_total if component_total > 0 else row.uang_jalan
        if total <= 0:
            continue
        db.add(
            CustomerVehicleTariff(
                customer_id=customer_id,
                vehicle_type_id=row.vehicle_type_id,
                bbm=row.bbm,
                tol=toll,
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


@router.post("/customers/refresh-stale-toll")
def refresh_stale_customer_toll(db: Session = Depends(get_db)):
    """Recalculate custom_toll_breakdown for customers that have stale (Rp 0) segments."""
    from app.routing_service import calculate_route

    warehouse = _get_or_create_warehouse(db)
    if not warehouse or warehouse.latitude is None or warehouse.longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Koordinat gudang belum diatur.",
        )

    origin_lat = float(warehouse.latitude)
    origin_lng = float(warehouse.longitude)

    sections = _load_active_toll_sections(db)
    gate_context = _load_toll_gate_fare_context(db)

    customers = db.scalars(
        select(Customer).where(Customer.custom_toll_breakdown.isnot(None))
    ).all()

    updated = 0
    skipped = 0
    errors: list[str] = []

    for cust in customers:
        if cust.latitude is None or cust.longitude is None:
            skipped += 1
            continue

        try:
            old_segments = json.loads(cust.custom_toll_breakdown)
        except (json.JSONDecodeError, TypeError):
            skipped += 1
            continue

        # Check if any segments have one_way_idr == 0 with source "route"
        has_stale = any(
            (not seg.get("_route_meta"))
            and seg.get("one_way_idr", 0) == 0
            and seg.get("source") == "route"
            for seg in old_segments
        )
        if not has_stale:
            skipped += 1
            continue

        dest_lat = float(cust.latitude)
        dest_lng = float(cust.longitude)

        try:
            route = calculate_route(
                origin_lat, origin_lng,
                dest_lat, dest_lng,
                sections=sections,
                force_toll=cust.force_toll,
                gate_context=gate_context,
                prefer_cheapest_toll=True,
            )
            new_segments = route.get("toll_breakdown")
            if new_segments:
                # Merge: keep any manually edited segments, replace stale route segments
                new_by_name = {}
                for seg in new_segments:
                    key = (seg.get("section_name") or "").strip().lower()
                    new_by_name[key] = seg

                merged = []
                for old_seg in old_segments:
                    if old_seg.get("_route_meta"):
                        merged.append(old_seg)
                        continue
                    key = (old_seg.get("section_name") or "").strip().lower()
                    if old_seg.get("one_way_idr", 0) == 0 and old_seg.get("source") == "route":
                        # Replace stale segment with fresh data if available
                        new_seg = new_by_name.get(key)
                        if new_seg and float(new_seg.get("one_way_idr") or 0) > 0:
                            merged.append(new_seg)
                        else:
                            merged.append(old_seg)
                    else:
                        merged.append(old_seg)

                has_changes = any(
                    m.get("one_way_idr", 0) != o.get("one_way_idr", 0)
                    for m, o in zip(merged, old_segments)
                )
                if has_changes:
                    cust.custom_toll_breakdown = json.dumps(merged)
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        except Exception as exc:
            errors.append(f"Customer {cust.id} ({cust.name}): {exc}")
            skipped += 1

    db.commit()

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:10],
        "total": len(customers),
    }


@router.get("/customers/lock-restore-status", response_model=CustomerLockRestoreStatusOut)
def finance_lock_restore_status(
    user: User = Depends(require_permission("customers:read")),
    db: Session = Depends(get_db),
):
    """Status snapshot customer yang menunggu dikunci kembali setelah unlock-all.

    Harus dideklarasikan sebelum ``/customers/{customer_id}`` agar path tidak
    tertangkap sebagai ID.
    """
    if user.role != Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Hanya Admin yang dapat melihat status kunci kembali.",
        )
    pending = _finance_lock_restore_ids(db)
    return CustomerLockRestoreStatusOut(
        pending_count=len(pending),
        message=(
            f"{len(pending)} customer menunggu dikunci kembali."
            if pending
            else "Tidak ada antrian kunci kembali."
        ),
    )


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
    # Kunci Finance: diatur di Matriks Akses (menu "Kunci Finance Customer").
    can_manage_finance_lock = has_permission(
        current_user.role, CUSTOMER_FINANCE_LOCK_PERMISSION
    )
    locked_finance = bool(payload.is_locked_finance) if can_manage_finance_lock else False
    if locked_finance and not payload.is_locked_marketing:
        raise HTTPException(
            status_code=400,
            detail="Kunci Finance hanya dapat dilakukan jika Kunci Marketing sudah aktif.",
        )
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
        is_locked_finance=locked_finance,
        updated_at=func.now(),
        updated_by_id=current_user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        share_location=payload.share_location,
        custom_toll_breakdown=(
            json.dumps(payload.custom_toll_breakdown)
            if payload.custom_toll_breakdown is not None
            else None
        ),
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

    # Kunci Finance: hak diatur di Matriks Akses → "Kunci Finance Customer" (Lihat & Edit).
    can_manage_finance_lock = has_permission(
        current_user.role, CUSTOMER_FINANCE_LOCK_PERMISSION
    )

    if bool(payload.is_locked_finance) != bool(obj.is_locked_finance) and not can_manage_finance_lock:
        raise HTTPException(
            status_code=403,
            detail="Anda tidak berwenang mengubah Kunci Finance. Atur di Matriks Akses (Kunci Finance Customer).",
        )

    if obj.is_locked_finance and not can_manage_finance_lock:
        raise HTTPException(
            status_code=403,
            detail="Customer telah dikunci final (Finance). Hanya role dengan hak Kunci Finance yang dapat membuka kunci.",
        )

    if current_user.role == Role.MARKETING.value:
        if obj.is_locked_marketing and payload.is_locked_marketing:
            raise HTTPException(
                status_code=403,
                detail="Customer telah dikunci. Hilangkan centang Kunci Marketing terlebih dahulu untuk menyimpan perubahan.",
            )

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

    obj.is_locked_marketing = payload.is_locked_marketing
    if can_manage_finance_lock:
        obj.is_locked_finance = payload.is_locked_finance
    # Role tanpa hak matriks: is_locked_finance tidak diubah

    obj.updated_at = func.now()
    obj.updated_by_id = current_user.id
    obj.latitude = payload.latitude
    obj.longitude = payload.longitude
    obj.share_location = payload.share_location
    obj.custom_toll_breakdown = (
        json.dumps(payload.custom_toll_breakdown)
        if payload.custom_toll_breakdown is not None
        else None
    )

    try:
        _replace_customer_tariffs(db, obj.id, payload.tariffs)
        refresh_customer_tariff_in_sales(db, obj.id)
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    db.refresh(obj)
    return _serialize_customer(db, obj)


def _get_or_create_app_setting(db: Session) -> AppSetting:
    setting = db.scalars(select(AppSetting).limit(1)).first()
    if setting:
        return setting
    setting = AppSetting()
    db.add(setting)
    db.flush()
    return setting


def _finance_lock_restore_ids(db: Session) -> list[int]:
    setting = db.scalars(select(AppSetting).limit(1)).first()
    raw = (setting.finance_lock_restore_ids if setting else None) or ""
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    ids: list[int] = []
    for item in data:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _set_finance_lock_restore_ids(db: Session, ids: list[int] | None) -> None:
    setting = _get_or_create_app_setting(db)
    if not ids:
        setting.finance_lock_restore_ids = None
    else:
        setting.finance_lock_restore_ids = json.dumps(sorted({int(i) for i in ids}))


@router.post("/customers/unlock-all", response_model=CustomerUnlockAllOut)
def unlock_all_customers(
    user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
):
    """Buka kunci Finance (Final) untuk SEMUA Master Customer — hanya Admin.

    Menyimpan daftar ID yang dibuka agar bisa dikunci kembali lewat
    ``relock-previous`` setelah sinkronisasi. Kunci Marketing tidak diubah.
    """
    if user.role != Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Hanya Admin yang dapat membuka kunci semua Master Customer.",
        )

    locked_ids = list(
        db.scalars(select(Customer.id).where(Customer.is_locked_finance.is_(True))).all()
    )
    locked_finance_count = len(locked_ids)

    if locked_finance_count == 0:
        pending = _finance_lock_restore_ids(db)
        return CustomerUnlockAllOut(
            unlocked_count=0,
            unlocked_finance_count=0,
            unlocked_marketing_count=0,
            restore_pending_count=len(pending),
            message="Tidak ada Master Customer yang terkunci Finance.",
        )

    previous = set(_finance_lock_restore_ids(db))
    merged = sorted(previous | set(locked_ids))
    _set_finance_lock_restore_ids(db, merged)

    db.execute(
        update(Customer)
        .where(Customer.is_locked_finance.is_(True))
        .values(
            is_locked_finance=False,
            updated_at=func.now(),
            updated_by_id=user.id,
        )
    )
    db.commit()

    return CustomerUnlockAllOut(
        unlocked_count=locked_finance_count,
        unlocked_finance_count=locked_finance_count,
        unlocked_marketing_count=0,
        restore_pending_count=len(merged),
        message=(
            f"Berhasil membuka kunci Finance {locked_finance_count} Master Customer. "
            f"Setelah sync, gunakan 'Kunci Kembali Sebelumnya' "
            f"({len(merged)} customer)."
        ),
    )


@router.post("/customers/relock-previous", response_model=CustomerRelockPreviousOut)
def relock_previous_finance_customers(
    user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
):
    """Kunci ulang Finance hanya untuk customer yang sebelumnya dibuka via unlock-all."""
    if user.role != Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Hanya Admin yang dapat mengunci kembali customer sebelumnya.",
        )

    restore_ids = _finance_lock_restore_ids(db)
    if not restore_ids:
        return CustomerRelockPreviousOut(
            locked_count=0,
            message="Tidak ada antrian kunci kembali. Buka kunci semua dulu sebelum sync.",
        )

    existing_rows = list(
        db.scalars(select(Customer).where(Customer.id.in_(restore_ids))).all()
    )
    existing_ids = {c.id for c in existing_rows}
    skipped_missing = len(restore_ids) - len(existing_ids)

    already_locked = [c for c in existing_rows if c.is_locked_finance]
    to_lock = [c for c in existing_rows if not c.is_locked_finance]

    if to_lock:
        lock_ids = [c.id for c in to_lock]
        db.execute(
            update(Customer)
            .where(Customer.id.in_(lock_ids))
            .values(
                is_locked_finance=True,
                is_locked_marketing=True,
                updated_at=func.now(),
                updated_by_id=user.id,
            )
        )

    _set_finance_lock_restore_ids(db, None)
    db.commit()

    locked_count = len(to_lock)
    skipped_already = len(already_locked)
    return CustomerRelockPreviousOut(
        locked_count=locked_count,
        skipped_already_locked=skipped_already,
        skipped_missing=skipped_missing,
        pending_count=0,
        message=(
            f"Berhasil mengunci kembali {locked_count} Master Customer"
            + (
                f" ({skipped_already} sudah terkunci sebelumnya)."
                if skipped_already
                else "."
            )
            + (
                f" {skipped_missing} ID tidak ditemukan (mungkin sudah dihapus)."
                if skipped_missing
                else ""
            )
        ),
    )


@router.post("/customers/lock-all", response_model=CustomerLockAllOut)
def lock_all_customers(
    user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
):
    """Kunci Finance (Final) untuk SEMUA Master Customer — hanya Admin.

    Kunci Marketing ikut diaktifkan bila belum aktif, karena Kunci Finance
    mensyaratkan Kunci Marketing.
    """
    if user.role != Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Hanya Admin yang dapat mengunci semua Master Customer.",
        )

    unlocked_finance_count = db.scalar(
        select(func.count()).select_from(Customer).where(Customer.is_locked_finance.is_(False))
    ) or 0
    marketing_ensured_count = db.scalar(
        select(func.count())
        .select_from(Customer)
        .where(
            Customer.is_locked_finance.is_(False),
            Customer.is_locked_marketing.is_(False),
        )
    ) or 0

    if unlocked_finance_count == 0:
        return CustomerLockAllOut(
            locked_count=0,
            locked_finance_count=0,
            marketing_ensured_count=0,
            message="Semua Master Customer sudah terkunci Finance.",
        )

    db.execute(
        update(Customer)
        .where(Customer.is_locked_finance.is_(False))
        .values(
            is_locked_finance=True,
            is_locked_marketing=True,
            updated_at=func.now(),
            updated_by_id=user.id,
        )
    )
    _set_finance_lock_restore_ids(db, None)
    db.commit()

    return CustomerLockAllOut(
        locked_count=unlocked_finance_count,
        locked_finance_count=unlocked_finance_count,
        marketing_ensured_count=marketing_ensured_count,
        message=(
            f"Berhasil mengunci Finance {unlocked_finance_count} Master Customer"
            + (
                f" (Kunci Marketing diaktifkan untuk {marketing_ensured_count} customer)."
                if marketing_ensured_count
                else "."
            )
        ),
    )


@router.post("/customers/{customer_id}/unlock-finance", response_model=CustomerOut)
def unlock_customer_finance(
    customer_id: int,
    user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
):
    """Buka kunci Finance (Final) — role dengan hak Matriks Akses 'Kunci Finance Customer'."""
    if not has_permission(user.role, CUSTOMER_FINANCE_LOCK_PERMISSION):
        raise HTTPException(
            status_code=403,
            detail="Anda tidak berwenang membuka kunci Finance. Atur di Matriks Akses (Kunci Finance Customer).",
        )
    obj = db.execute(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not obj.is_locked_finance:
        raise HTTPException(status_code=400, detail="Customer tidak dalam status terkunci Finance.")

    obj.is_locked_finance = False
    obj.updated_at = func.now()
    obj.updated_by_id = user.id
    db.commit()
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
        from app.customer_tariff_sync import propagate_bbm_uang_mel_to_customers

        propagate_bbm_uang_mel_to_customers(db, bbm_id=bbm_id)
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
        from app.customer_tariff_sync import propagate_bbm_uang_mel_to_customers

        propagate_bbm_uang_mel_to_customers(db, uang_mel_id=mel_id)
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


@router.get("/uang-pelabuhan", response_model=list[UangPelabuhanOut])
def list_uang_pelabuhan(db: Session = Depends(get_db)):
    return db.scalars(
        select(UangPelabuhanMaster).order_by(UangPelabuhanMaster.name.asc())
    ).all()


@router.post("/uang-pelabuhan", response_model=UangPelabuhanOut, status_code=201)
def create_uang_pelabuhan(payload: UangPelabuhanCreate, db: Session = Depends(get_db)):
    obj = UangPelabuhanMaster(name=payload.name.strip(), amount=payload.amount)
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.put("/uang-pelabuhan/{pelabuhan_id}", response_model=UangPelabuhanOut)
def update_uang_pelabuhan(
    pelabuhan_id: int, payload: UangPelabuhanCreate, db: Session = Depends(get_db)
):
    obj = db.get(UangPelabuhanMaster, pelabuhan_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Master Uang Pelabuhan tidak ditemukan")
    obj.name = payload.name.strip()
    obj.amount = payload.amount
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.delete("/uang-pelabuhan/{pelabuhan_id}", status_code=204)
def delete_uang_pelabuhan(pelabuhan_id: int, db: Session = Depends(get_db)):
    obj = db.get(UangPelabuhanMaster, pelabuhan_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Master Uang Pelabuhan tidak ditemukan")
    in_use = db.scalar(
        select(func.count())
        .select_from(VehicleType)
        .where(VehicleType.uang_pelabuhan_id == pelabuhan_id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Uang Pelabuhan masih dipakai jenis kendaraan. Ubah jenis kendaraan tersebut dulu.",
        )
    db.delete(obj)
    db.commit()


@router.get("/route-fees/{fee_type}", response_model=list[RouteFeeOut])
def list_route_fees(fee_type: str, db: Session = Depends(get_db)):
    try:
        get_route_fee_def(fee_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return db.scalars(
        select(RouteFeeMaster)
        .where(RouteFeeMaster.fee_type == fee_type)
        .order_by(RouteFeeMaster.name.asc())
    ).all()


@router.post("/route-fees/{fee_type}", response_model=RouteFeeOut, status_code=201)
def create_route_fee(fee_type: str, payload: RouteFeeCreate, db: Session = Depends(get_db)):
    try:
        get_route_fee_def(fee_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    obj = RouteFeeMaster(fee_type=fee_type, name=payload.name.strip(), amount=payload.amount)
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.put("/route-fees/{fee_type}/{fee_id}", response_model=RouteFeeOut)
def update_route_fee(
    fee_type: str, fee_id: int, payload: RouteFeeCreate, db: Session = Depends(get_db)
):
    obj = db.get(RouteFeeMaster, fee_id)
    if not obj or obj.fee_type != fee_type:
        raise HTTPException(status_code=404, detail="Master biaya rute tidak ditemukan")
    obj.name = payload.name.strip()
    obj.amount = payload.amount
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e) from e
    db.refresh(obj)
    return obj


@router.delete("/route-fees/{fee_type}/{fee_id}", status_code=204)
def delete_route_fee(fee_type: str, fee_id: int, db: Session = Depends(get_db)):
    obj = db.get(RouteFeeMaster, fee_id)
    if not obj or obj.fee_type != fee_type:
        raise HTTPException(status_code=404, detail="Master biaya rute tidak ditemukan")
    db.delete(obj)
    db.commit()


def _load_vehicle_types_query():
    return (
        select(VehicleType)
        .options(
            selectinload(VehicleType.toll_golongan),
            selectinload(VehicleType.bbm),
            selectinload(VehicleType.uang_mel),
            selectinload(VehicleType.uang_pelabuhan),
        )
        .order_by(VehicleType.name.asc())
    )


@router.get("/vehicle-types", response_model=list[VehicleTypeOut])
def list_vehicle_types(db: Session = Depends(get_db)):
    rows = db.scalars(_load_vehicle_types_query()).all()
    return [_vehicle_type_out(row, db) for row in rows]


@router.post("/vehicle-types", response_model=VehicleTypeOut, status_code=201)
def create_vehicle_type(payload: VehicleTypeCreate, db: Session = Depends(get_db)):
    _validate_toll_golongan_id(db, payload.toll_golongan_id)
    _validate_bbm_id(db, payload.bbm_id)
    _validate_uang_mel_id(db, payload.uang_mel_id)
    _validate_uang_pelabuhan_id(db, payload.uang_pelabuhan_id)
    obj = VehicleType(
        name=payload.name.strip(),
        toll_golongan_id=payload.toll_golongan_id,
        bbm_id=payload.bbm_id,
        uang_mel_id=payload.uang_mel_id,
        uang_pelabuhan_id=payload.uang_pelabuhan_id,
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
    return _vehicle_type_out(obj, db)


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
    _validate_uang_pelabuhan_id(db, payload.uang_pelabuhan_id)
    obj.name = payload.name.strip()
    obj.toll_golongan_id = payload.toll_golongan_id
    obj.bbm_id = payload.bbm_id
    obj.uang_mel_id = payload.uang_mel_id
    obj.uang_pelabuhan_id = payload.uang_pelabuhan_id
    obj.km_per_liter = payload.km_per_liter
    try:
        from app.customer_tariff_sync import propagate_bbm_uang_mel_to_customers

        propagate_bbm_uang_mel_to_customers(db, vehicle_type_id=type_id)
        db.commit()
    except Exception as e:
        db.rollback()
        raise _unique_violation_to_409(e)
    obj = db.scalar(_load_vehicle_types_query().where(VehicleType.id == type_id))
    return _vehicle_type_out(obj, db)


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


@router.get("/reports/customer-tariffs", response_model=list[CustomerTariffReportRow])
def report_customer_tariffs(
    customer_id: int | None = None,
    active_only: bool = Query(True),
    filled_only: bool = Query(True),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("reports:read")),
):
    """Master tarif uang jalan per customer (BBM, Tol, Uang Mel, Parkir, Lain-lain)."""
    return customer_tariff_report(
        db,
        customer_id=customer_id,
        active_only=active_only,
        filled_only=filled_only,
    )


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
        route_fees = sum_route_fees(s)
        multi = len(detail_rows) > 1
        base_uang_jalan = max_nominal if multi else (detail_rows[0]["amount"] if detail_rows else 0)
        totals = compute_uang_jalan_totals(base_uang_jalan, extra, route_fees)

        results.append({
            "id": s.id,
            "sale_no": s.sale_no,
            "date": s.date.isoformat(),
            "vehicle_plate": vehicle.plate_number if vehicle else "-",
            "driver_name": driver.name if driver else "-",
            "remarks": s.remarks,
            "customers": ", ".join(d["customer_name"] for d in detail_rows),
            "customers_list": [d["customer_name"] for d in detail_rows],
            "vehicle_type": ", ".join(set(d["vehicle_type_name"] for d in detail_rows)),
            "uang_jalan": base_uang_jalan,
            "extra_uang_jalan": extra,
            "include_uang_pelabuhan": bool(s.include_uang_pelabuhan),
            "uang_pelabuhan": float(s.uang_pelabuhan or 0) if s.include_uang_pelabuhan else 0.0,
            "route_fees_total": route_fees,
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
        include_uang_pelabuhan=bool(obj.include_uang_pelabuhan),
        uang_pelabuhan=float(obj.uang_pelabuhan or 0),
        include_pjr=bool(obj.include_pjr),
        pjr=float(obj.pjr or 0),
        include_forklift_bongkaran=bool(obj.include_forklift_bongkaran),
        forklift_bongkaran=float(obj.forklift_bongkaran or 0),
        include_parkir_liar=bool(obj.include_parkir_liar),
        parkir_liar=float(obj.parkir_liar or 0),
        include_parkir_kawasan=bool(obj.include_parkir_kawasan),
        parkir_kawasan=float(obj.parkir_kawasan or 0),
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
        include_uang_pelabuhan=bool(route.include_uang_pelabuhan),
        uang_pelabuhan=float(route.uang_pelabuhan or 0),
        include_pjr=bool(route.include_pjr),
        pjr=float(route.pjr or 0),
        include_forklift_bongkaran=bool(route.include_forklift_bongkaran),
        forklift_bongkaran=float(route.forklift_bongkaran or 0),
        include_parkir_liar=bool(route.include_parkir_liar),
        parkir_liar=float(route.parkir_liar or 0),
        include_parkir_kawasan=bool(route.include_parkir_kawasan),
        parkir_kawasan=float(route.parkir_kawasan or 0),
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
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    finance_status: str | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(Sale)
    if from_date:
        stmt = stmt.where(Sale.date >= from_date)
    if to_date:
        stmt = stmt.where(Sale.date <= to_date)
    if driver_id:
        stmt = stmt.where(Sale.driver_id == driver_id)
    if vehicle_id:
        stmt = stmt.where(Sale.vehicle_id == vehicle_id)
    if finance_status == "paid":
        stmt = stmt.where(Sale.finance_paid_at.isnot(None), Sale.is_void == False)
    elif finance_status == "pending":
        stmt = stmt.where(Sale.finance_paid_at.is_(None), Sale.is_void == False)
    elif finance_status == "void":
        stmt = stmt.where(Sale.is_void == True)
    term = (sale_no or "").strip()
    if term:
        like = f"%{term}%"
        plate_compact = term.replace(" ", "")
        stmt = stmt.where(
            or_(
                Sale.sale_no.ilike(like),
                Sale.delivery_route_id.in_(
                    select(DeliveryRoute.id).where(DeliveryRoute.route_no.ilike(like))
                ),
                Sale.driver_id.in_(
                    select(Driver.id).where(Driver.name.ilike(like))
                ),
                Sale.vehicle_id.in_(
                    select(Vehicle.id).where(
                        or_(
                            Vehicle.plate_number.ilike(like),
                            func.replace(Vehicle.plate_number, " ", "").ilike(
                                f"%{plate_compact}%"
                            ),
                        )
                    )
                ),
            )
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
    apply_route_fees_from_payload(db, obj, payload.vehicle_type_id, payload)
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
    apply_route_fees_from_payload(db, obj, payload.vehicle_type_id, payload)
    if payload.route_no:
        obj.route_no = payload.route_no
    replace_route_stops(db, obj, payload.stops)
    sale = route_sale(db, route_id)
    if sale and not sale_finance_locked(sale):
        from app.delivery_route_service import sync_sale_from_route

        sync_sale_from_route(db, obj)
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


def _sanitize_route_profile_for_user(
    payload: RouteProcessRequest,
    user: User,
    customer: Customer | None = None,
) -> RouteProcessRequest:
    """Default otomatis OSRM; ruas tol manual tetap dipakai jika section_ids dikirim."""
    if payload.section_ids:
        return payload.model_copy(update={"route_profile": "manual"})
    return payload.model_copy(update={"route_profile": "auto", "section_ids": None})


@router.post("/routing/process", response_model=RouteProcessOut)
def process_route(
    payload: RouteProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_access),
):
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

    payload = _sanitize_route_profile_for_user(payload, current_user, customer)

    sections_full = _load_active_toll_sections(db, collapse=False)
    sections_auto = collapse_sections_for_routing(sections_full)
    gate_context = _load_toll_gate_fare_context(db)
    vehicle_types = db.scalars(_load_vehicle_types_query()).all()

    section_ids, profile_key = _resolve_route_section_ids(
        payload, customer, sections_full, dest_lat, dest_lng
    )
    requested_profile = (payload.route_profile or "auto").strip().lower()
    profile_label = next(
        (p["label"] for p in list_route_profiles() if p["key"] == profile_key),
        None,
    )

    if section_ids:
        adapt_note = profile_adaptation_note(requested_profile, dest_lat, dest_lng)
        note_prefix = adapt_note or (f"Skema: {profile_label}." if profile_label else None)
        route, toll_by_vehicle_raw = _build_corridor_route(
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            section_ids=section_ids,
            sections=sections_full,
            gate_context=gate_context,
            force_toll=bool(payload.force_toll),
            vehicle_types=vehicle_types,
            note_prefix=note_prefix,
            distance_provider=(payload.distance_provider or "osrm"),
        )
        route["route_profile"] = profile_key
    else:
        route = calculate_route(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            sections=sections_auto,
            force_toll=payload.force_toll,
            gate_context=gate_context,
            prefer_cheapest_toll=bool(payload.prefer_cheapest_toll),
            distance_provider=(payload.distance_provider or "osrm"),
        )
        route["route_profile"] = profile_key if profile_key not in ("auto", "") else None
        route["route_via_toll_gates"] = False

        if gate_context.get("fares") and not route["toll_is_estimate"]:
            toll_by_vehicle_raw = []
            for vt in vehicle_types:
                gol_code = vt.toll_golongan.code if vt.toll_golongan else "II"
                meta = VEHICLE_TOLL_CLASS.get(
                    _match_toll_vehicle_key(vt.name) or "", {}
                )
                if vehicle_toll_allowed(vt.name):
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
                        sections=sections_full,
                    )
                    toll = round(bpjt[0] * 2, 0) if bpjt else route["toll_idr"]
                else:
                    toll = 0.0
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
                sections=sections_auto,
            )
        if toll_by_vehicle_raw:
            route["toll_idr"] = toll_by_vehicle_raw[0]["toll_idr"]

    if customer is not None:
        customer_name = customer.name
        customer_id = customer.id
        dest_address = ", ".join(p for p in [customer.address, customer.city] if p)
    else:
        customer_name = payload.name or "Partner"
        customer_id = None
        dest_address = None

    origin_address = ", ".join(p for p in [warehouse.address, warehouse.city] if p)

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


@router.get("/routing/route-profiles", response_model=list[RouteProfileOut])
def get_route_profiles():
    return [RouteProfileOut(**item) for item in list_route_profiles()]


@router.post("/routing/toll-breakdown/manual", response_model=ManualTollBreakdownOut)
def manual_toll_breakdown(
    payload: ManualTollBreakdownRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_access),
):
    # Jangan collapse: exit-variant (Karawaci, Cikupa, Merak, …) harus resolve by id.
    sections = _load_active_toll_sections(db, collapse=False)
    gate_context = _load_toll_gate_fare_context(db)
    result = build_manual_toll_breakdown(
        payload.section_ids,
        sections,
        gate_context.get("gates") or [],
        gate_context.get("fares") or [],
        golongan_code="II",
    )
    return ManualTollBreakdownOut(**result)


@router.post("/routing/recalculate-with-sections", response_model=RouteRecalculateOut)
def recalculate_route_with_sections(
    payload: RouteRecalculateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_access),
):
    warehouse = _get_or_create_warehouse(db)
    try:
        origin_lat, origin_lng = (
            (float(warehouse.latitude), float(warehouse.longitude))
            if warehouse.latitude is not None and warehouse.longitude is not None
            else geocode_address(
                warehouse.address,
                warehouse.kelurahan,
                warehouse.kecamatan,
                warehouse.city,
                warehouse.name,
            )
        )
    except HTTPException:
        raise HTTPException(
            status_code=400,
            detail="Koordinat gudang belum diatur. Isi alamat gudang di menu Gudang.",
        )

    dest_lat = float(payload.latitude)
    dest_lng = float(payload.longitude)
    sections = _load_active_toll_sections(db, collapse=False)
    gate_context = _load_toll_gate_fare_context(db)
    vehicle_types = db.scalars(_load_vehicle_types_query()).all()

    route, toll_by_vehicle_raw = _build_corridor_route(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        section_ids=payload.section_ids,
        sections=sections,
        gate_context=gate_context,
        force_toll=bool(payload.force_toll),
        vehicle_types=vehicle_types,
        distance_provider=(payload.distance_provider or "osrm"),
    )

    return RouteRecalculateOut(
        distance_km=route["distance_km"],
        duration_min=route["duration_min"],
        distance_source=route.get("distance_source") or "osrm",
        distance_km_route=route.get("distance_km_route"),
        duration_min_route=route.get("duration_min_route"),
        distance_km_direct=route.get("distance_km_direct"),
        duration_min_direct=route.get("duration_min_direct"),
        geometry=route.get("geometry") or [],
        toll_roads=route.get("toll_roads") or [],
        toll_breakdown=route["toll_breakdown"],
        toll_idr=route["toll_idr"],
        toll_is_estimate=route["toll_is_estimate"],
        toll_note=route["toll_note"],
        toll_source=route["toll_source"],
        toll_by_vehicle=[VehicleTollEstimate(**item) for item in toll_by_vehicle_raw],
        route_via_toll_gates=route.get("route_via_toll_gates", False),
        route_profile="manual",
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


