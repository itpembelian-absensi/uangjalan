from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.roles import ROLE_PATTERN


class CustomerTariffItem(BaseModel):
    vehicle_type_id: int
    bbm: float = Field(ge=0, default=0)
    tol: float = Field(ge=0, default=0)
    uang_mel: float = Field(ge=0, default=0)
    parkir: float = Field(ge=0, default=0)
    lain_lain: float = Field(ge=0, default=0)
    uang_jalan: float = Field(ge=0, default=0)


class CustomerTariffOut(CustomerTariffItem):
    vehicle_type_name: str | None = None


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1)
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    latitude: float | None = None
    longitude: float | None = None
    force_toll: bool = False
    is_locked_marketing: bool = False
    is_locked_finance: bool = False
    custom_toll_breakdown: list[dict] | None = None
    share_location: str | None = None
    tariffs: list[CustomerTariffItem] = Field(default_factory=list)


class CustomerBulkImportItem(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1)
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class CustomerBulkImport(BaseModel):
    customers: list[CustomerBulkImportItem]


class CustomerUnlockAllOut(BaseModel):
    unlocked_count: int
    unlocked_finance_count: int
    unlocked_marketing_count: int
    restore_pending_count: int = 0
    message: str


class CustomerLockAllOut(BaseModel):
    locked_count: int
    locked_finance_count: int
    marketing_ensured_count: int
    message: str


class CustomerLockRestoreStatusOut(BaseModel):
    pending_count: int
    message: str


class CustomerRelockPreviousOut(BaseModel):
    locked_count: int
    skipped_already_locked: int = 0
    skipped_missing: int = 0
    pending_count: int = 0
    message: str


class CustomerOut(BaseModel):
    id: int
    code: str | None = None
    name: str
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    latitude: float | None = None
    longitude: float | None = None
    force_toll: bool
    custom_toll_breakdown: list[dict] | None = None
    share_location: str | None = None
    tariffs: list[CustomerTariffOut] = Field(default_factory=list)
    created_at: datetime
    is_locked_marketing: bool
    is_locked_finance: bool
    updated_at: datetime | None = None
    updated_by_name: str | None = None

    class Config:
        from_attributes = True


class CustomerListOut(BaseModel):
    id: int
    code: str | None = None
    name: str
    phone: str | None = None
    is_active: bool
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    force_toll: bool
    is_locked_marketing: bool
    is_locked_finance: bool
    updated_at: datetime | None = None
    updated_by_name: str | None = None

    class Config:
        from_attributes = True


class VehicleBrandCreate(BaseModel):
    name: str = Field(min_length=1)


class VehicleBrandOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class BbmCreate(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)


class BbmOut(BaseModel):
    id: int
    name: str
    price: float
    created_at: datetime

    class Config:
        from_attributes = True


class UangMelCreate(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(ge=0)


class UangMelOut(BaseModel):
    id: int
    name: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class UangPelabuhanCreate(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(ge=0)


class UangPelabuhanOut(BaseModel):
    id: int
    name: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class RouteFeeCreate(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(ge=0)


class RouteFeeOut(BaseModel):
    id: int
    fee_type: str
    name: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class VehicleTypeCreate(BaseModel):
    name: str = Field(min_length=1)
    toll_golongan_id: int | None = None
    bbm_id: int | None = None
    uang_mel_id: int | None = None
    uang_pelabuhan_id: int | None = None
    km_per_liter: float | None = Field(default=None, gt=0)


class VehicleTypeOut(BaseModel):
    id: int
    name: str
    toll_golongan_id: int | None = None
    toll_golongan_name: str | None = None
    toll_golongan_code: str | None = None
    bbm_id: int | None = None
    bbm_name: str | None = None
    bbm_price: float | None = None
    uang_mel_id: int | None = None
    uang_mel_name: str | None = None
    uang_mel_amount: float = 0
    uang_pelabuhan_id: int | None = None
    uang_pelabuhan_name: str | None = None
    uang_pelabuhan_amount: float = 0
    km_per_liter: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class VehicleCreate(BaseModel):
    plate_number: str = Field(min_length=1)
    brand_id: int
    type_id: int | None = None


class VehicleOut(BaseModel):
    id: int
    plate_number: str
    brand_id: int
    type_id: int | None = None
    type_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DriverCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None


class DriverOut(BaseModel):
    id: int
    name: str
    phone: str | None
    bank_name: str | None = None
    bank_account: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CashDisbursementCreate(BaseModel):
    customer_id: int
    vehicle_type_id: int | None = None
    amount: float = Field(gt=0)
    description: str | None = None
    disbursed_at: datetime | None = None


class CashDisbursementOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None = None
    vehicle_type_id: int | None
    vehicle_type_name: str | None = None
    amount: float
    description: str | None
    disbursed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class DriverSummaryRow(BaseModel):
    driver_id: int
    driver_name: str
    delivery_count: int
    total_amount: float


class CustomerSummaryRow(BaseModel):
    customer_id: int
    customer_name: str
    delivery_count: int
    total_amount: float


class CustomerTariffReportRow(BaseModel):
    customer_id: int
    customer_code: str | None = None
    customer_name: str
    is_active: bool = True
    vehicle_type_id: int
    vehicle_type_name: str
    bbm: float = 0
    tol: float = 0
    uang_mel: float = 0
    parkir: float = 0
    lain_lain: float = 0
    uang_jalan: float = 0


class DisbursementDetailRow(BaseModel):
    id: int
    disbursed_at: datetime
    customer_name: str
    vehicle_type_name: str
    amount: float
    description: str | None


class DeliveryRouteStopLineItem(BaseModel):
    item_name: str = Field(min_length=1)
    quantity: float = Field(gt=0)


class DeliveryRouteStopLineOut(BaseModel):
    id: int
    item_name: str
    quantity: float
    sort_order: int

    class Config:
        from_attributes = True


class DeliveryRouteStopItem(BaseModel):
    customer_id: int
    description: str | None = None
    entity_code: str | None = None
    items: list[DeliveryRouteStopLineItem] = Field(default_factory=list)


class DeliveryRouteStopOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None = None
    sort_order: int
    description: str | None = None
    entity_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    items: list[DeliveryRouteStopLineOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DeliveryRouteCreate(BaseModel):
    route_no: str | None = None
    date: date
    vehicle_type_id: int
    remarks: str | None = None
    ritase: int = Field(default=1, ge=1, le=10)
    include_uang_pelabuhan: bool = False
    include_pjr: bool = False
    include_forklift_bongkaran: bool = False
    include_parkir_liar: bool = False
    include_parkir_kawasan: bool = False
    stops: list[DeliveryRouteStopItem] = Field(default_factory=list, min_length=1)


class DeliveryRouteBulkSyncError(BaseModel):
    route_id: int
    route_no: str
    reason: str


class DeliveryRouteBulkSyncOut(BaseModel):
    total_routes: int
    created: int
    updated: int
    synced: int
    skipped_locked: int
    skipped_errors: list[DeliveryRouteBulkSyncError] = Field(default_factory=list)


class DeliveryRouteOut(BaseModel):
    id: int
    route_no: str
    date: date
    vehicle_type_id: int
    vehicle_type_name: str | None = None
    vehicle_id: int | None = None
    vehicle_plate: str | None = None
    driver_id: int | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    remarks: str | None = None
    ritase: int = 1
    include_uang_pelabuhan: bool = False
    uang_pelabuhan: float = 0
    include_pjr: bool = False
    pjr: float = 0
    include_forklift_bongkaran: bool = False
    forklift_bongkaran: float = 0
    include_parkir_liar: bool = False
    parkir_liar: float = 0
    include_parkir_kawasan: bool = False
    parkir_kawasan: float = 0
    stops: list[DeliveryRouteStopOut] = Field(default_factory=list)
    sale_id: int | None = None
    sale_no: str | None = None
    sale_vehicle_plate: str | None = None
    sale_driver_name: str | None = None
    is_finance_paid: bool = False
    finance_paid_at: datetime | None = None
    missing_tariff_customers: list[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class DeliveryRouteReportRouteRow(BaseModel):
    id: int
    route_no: str
    date: str
    vehicle_type_name: str
    stop_count: int
    customers: str
    ritase: int = 1
    remarks: str | None = None
    sale_no: str | None = None
    sale_vehicle_plate: str | None = None
    sale_driver_name: str | None = None


class DeliveryRouteReportItemLine(BaseModel):
    item_name: str
    quantity: float


class DeliveryRouteReportStopRow(BaseModel):
    route_no: str
    route_date: str
    vehicle_type_name: str
    stop_order: int
    customer_name: str
    description: str | None = None
    entity_code: str | None = None
    ritase: int = 1
    items: list[DeliveryRouteReportItemLine] = []
    items_qty_total: float = 0
    items_count: int = 0
    items_summary: str | None = None
    remarks: str | None = None
    sale_no: str | None = None
    sale_vehicle_plate: str | None = None
    sale_driver_name: str | None = None


class DeliveryRouteReportOut(BaseModel):
    total_routes: int
    total_stops: int
    total_items_qty: float = 0
    routes: list[DeliveryRouteReportRouteRow]
    stop_rows: list[DeliveryRouteReportStopRow]


class SaleDetailItem(BaseModel):
    customer_id: int
    vehicle_type_id: int
    amount: float = Field(ge=0, default=0)


class SaleDetailOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None = None
    customer_is_locked: bool = False
    vehicle_type_id: int | None = None
    vehicle_type_name: str | None = None
    amount: float = Field(ge=0, default=0)
    created_at: datetime

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    sale_no: str | None = None
    date: date
    vehicle_id: int | None = None
    driver_id: int | None = None
    remarks: str | None = None
    extra_uang_jalan: float = Field(ge=0, default=0)
    details: list[SaleDetailItem] = Field(default_factory=list, min_length=1)


class SaleOut(BaseModel):
    id: int
    sale_no: str
    date: date
    vehicle_id: int | None = None
    vehicle_plate: str | None = None
    driver_id: int | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    driver_bank_name: str | None = None
    driver_bank_account: str | None = None
    delivery_route_id: int | None = None
    route_no: str | None = None
    remarks: str | None = None
    extra_uang_jalan: float = Field(ge=0, default=0)
    include_uang_pelabuhan: bool = False
    uang_pelabuhan: float = Field(ge=0, default=0)
    include_pjr: bool = False
    pjr: float = Field(ge=0, default=0)
    include_forklift_bongkaran: bool = False
    forklift_bongkaran: float = Field(ge=0, default=0)
    include_parkir_liar: bool = False
    parkir_liar: float = Field(ge=0, default=0)
    include_parkir_kawasan: bool = False
    parkir_kawasan: float = Field(ge=0, default=0)
    details: list[SaleDetailOut] = Field(default_factory=list)
    is_finance_paid: bool = False
    finance_paid_at: datetime | None = None
    finance_paid_by_name: str | None = None
    is_void: bool = False
    void_reason: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SaleVoid(BaseModel):
    void_reason: str = Field(..., min_length=3)

    class Config:
        from_attributes = True


class WarehouseOut(BaseModel):
    id: int
    name: str
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    class Config:
        from_attributes = True


class WarehouseUpdate(BaseModel):
    name: str = Field(min_length=1)
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class RouteProcessRequest(BaseModel):
    customer_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    name: str | None = None
    force_toll: bool | None = False
    prefer_cheapest_toll: bool | None = False
    route_profile: str | None = "auto"
    section_ids: list[int] | None = None
    # "osrm" (koridor/default) | "osrm_direct" (mendekati Google, gratis) | "google"
    distance_provider: str | None = "osrm"


class RouteProfileOut(BaseModel):
    key: str
    label: str
    description: str | None = None


class RoutePoint(BaseModel):
    name: str
    address: str | None = None
    latitude: float
    longitude: float


class VehicleTollEstimate(BaseModel):
    vehicle_type_id: int
    vehicle_type_name: str
    golongan: str
    gandar: str
    toll_idr: float
    rate_per_km: float


class RouteTollSegmentOut(BaseModel):
    source: str
    section_name: str
    section_id: int | None = None
    entry_gate_code: str | None = None
    entry_gate_name: str | None = None
    exit_gate_code: str | None = None
    exit_gate_name: str | None = None
    detail: str | None = None
    weight_pct: float | None = None
    one_way_idr: float
    round_trip_idr: float
    rates_by_golongan: dict[str, float] | None = None


class RouteTollRoadOut(BaseModel):
    name: str
    latitude: float | None = None
    longitude: float | None = None
    geometry: list[list[float]] = Field(default_factory=list)


class RouteProcessOut(BaseModel):
    customer_id: int | None = None
    customer_name: str
    origin: RoutePoint
    destination: RoutePoint
    distance_km: float
    duration_min: float
    distance_source: str | None = "osrm"
    # Perbandingan: jarak rute/peta vs jarak langsung (≈ Google)
    distance_km_route: float | None = None
    duration_min_route: float | None = None
    distance_km_direct: float | None = None
    duration_min_direct: float | None = None
    toll_idr: float
    toll_is_estimate: bool
    toll_note: str | None = None
    toll_source: str = "none"
    toll_breakdown: list[RouteTollSegmentOut] = Field(default_factory=list)
    toll_roads: list[RouteTollRoadOut] = Field(default_factory=list)
    toll_by_vehicle: list[VehicleTollEstimate] = Field(default_factory=list)
    geometry: list[list[float]] = Field(default_factory=list)
    route_selection: str | None = None
    alternatives_compared: int = 0
    toll_savings_idr: float | None = None
    route_profile: str | None = None
    route_via_toll_gates: bool = False


class ManualTollBreakdownRequest(BaseModel):
    section_ids: list[int] = Field(min_length=1)


class ManualTollBreakdownOut(BaseModel):
    segments: list[RouteTollSegmentOut] = Field(default_factory=list)
    one_way_idr: float = 0.0
    toll_idr: float = 0.0
    toll_source: str = "manual"
    toll_is_estimate: bool = False
    toll_note: str | None = None


class RouteRecalculateRequest(BaseModel):
    latitude: float
    longitude: float
    section_ids: list[int] = Field(min_length=1)
    force_toll: bool | None = False
    distance_provider: str | None = "osrm"


class RouteRecalculateOut(BaseModel):
    distance_km: float
    duration_min: float
    distance_source: str | None = "osrm"
    distance_km_route: float | None = None
    duration_min_route: float | None = None
    distance_km_direct: float | None = None
    duration_min_direct: float | None = None
    geometry: list[list[float]] = Field(default_factory=list)
    toll_roads: list[RouteTollRoadOut] = Field(default_factory=list)
    toll_breakdown: list[RouteTollSegmentOut] = Field(default_factory=list)
    toll_idr: float
    toll_is_estimate: bool
    toll_note: str | None = None
    toll_source: str = "manual"
    toll_by_vehicle: list[VehicleTollEstimate] = Field(default_factory=list)
    route_via_toll_gates: bool = False
    route_profile: str | None = None


class GeocodeRequest(BaseModel):
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    name: str | None = None


class GeocodeFromShareRequest(BaseModel):
    text: str = Field(min_length=1)


class GeocodeOut(BaseModel):
    latitude: float
    longitude: float


class TollSectionRateOut(BaseModel):
    golongan_id: int
    golongan_name: str
    golongan_code: str
    rate: float


class TollSectionRateItem(BaseModel):
    golongan_id: int
    rate: float = Field(ge=0)


class TollSectionOut(BaseModel):
    id: int
    network: str | None = None
    name: str
    origin_name: str | None = None
    destination_name: str | None = None
    length_km: float
    sort_order: int
    is_active: bool
    rates: list[TollSectionRateOut] = Field(default_factory=list)


class TollSectionCreate(BaseModel):
    network: str | None = None
    name: str = Field(min_length=1)
    origin_name: str | None = None
    destination_name: str | None = None
    length_km: float = Field(gt=0)
    sort_order: int = 0
    is_active: bool = True
    rates: list[TollSectionRateItem] = Field(default_factory=list)


class TollSectionUpdate(BaseModel):
    network: str | None = None
    name: str | None = Field(default=None, min_length=1)
    origin_name: str | None = None
    destination_name: str | None = None
    length_km: float | None = Field(default=None, gt=0)
    sort_order: int | None = None
    is_active: bool | None = None
    rates: list[TollSectionRateItem] | None = None


class BpjtImportResultOut(BaseModel):
    network: str
    created: int
    updated: int
    total: int
    source_title: str | None = None
    source_page: str | None = None
    pdf_url: str | None = None
    source_modified: str | None = None


class BpjtGateImportResultOut(BaseModel):
    network: str
    sections_imported: int
    sections_skipped: list[str] = Field(default_factory=list)
    gates_created: int
    gates_updated: int
    fares_created: int
    source: str | None = None
    source_url: str | None = None


class TollGateCoordRefreshResultOut(BaseModel):
    updated: int
    skipped: list[str] = Field(default_factory=list)
    total: int


class BpjtFullImportResultOut(BaseModel):
    sections: BpjtImportResultOut
    gates: BpjtGateImportResultOut


class TollGolonganOut(BaseModel):
    id: int
    name: str
    code: str
    description: str | None = None
    sort_order: int
    is_active: bool


class TollGolonganCreate(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True


class TollGolonganUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    code: str | None = Field(default=None, min_length=1)
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TollGateOut(BaseModel):
    id: int
    section_id: int
    section_name: str | None = None
    code: str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    sort_order: int
    is_active: bool


class TollGateCreate(BaseModel):
    section_id: int
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    latitude: float | None = None
    longitude: float | None = None
    sort_order: int = 0
    is_active: bool = True


class TollGateUpdate(BaseModel):
    section_id: int | None = None
    code: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    latitude: float | None = None
    longitude: float | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TollGateFareOut(BaseModel):
    id: int
    section_id: int
    section_name: str | None = None
    entry_gate_id: int
    entry_gate_code: str
    entry_gate_name: str
    exit_gate_id: int
    exit_gate_code: str
    exit_gate_name: str
    golongan_id: int
    golongan_code: str
    golongan_name: str
    rate: float


class TollGateFareCreate(BaseModel):
    entry_gate_id: int
    exit_gate_id: int
    golongan_id: int
    rate: float = Field(ge=0)


class TollGateFareUpdate(BaseModel):
    entry_gate_id: int | None = None
    exit_gate_id: int | None = None
    golongan_id: int | None = None
    rate: float | None = Field(default=None, ge=0)


class TollReferenceOut(BaseModel):
    golongan: list[TollGolonganOut]
    sections: list[TollSectionOut]
    note: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=4, max_length=100)
    role: str = Field(pattern=ROLE_PATTERN)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=4, max_length=100)
    role: str | None = Field(default=None, pattern=ROLE_PATTERN)
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    role_label: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AuthUserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    role_label: str
    permissions: list[str]
    menus: list["MenuAccessOut"] = Field(default_factory=list)


class MenuAccessOut(BaseModel):
    id: str
    label: str
    path: str
    section: str
    icon: str
    can_write: bool
    access: str


class AccessMatrixRoleOut(BaseModel):
    id: str
    label: str


class AccessMatrixItemOut(BaseModel):
    id: str
    label: str
    path: str
    access: dict[str, str]


class AccessMatrixSectionOut(BaseModel):
    name: str
    items: list[AccessMatrixItemOut]


class AccessMatrixOut(BaseModel):
    roles: list[AccessMatrixRoleOut]
    sections: list[AccessMatrixSectionOut]
    legend: dict[str, str]
    can_edit: bool = False
    access_levels: list[str] = Field(default_factory=lambda: ["full", "read", "none"])


class AccessMatrixCellUpdate(BaseModel):
    menu_id: str = Field(min_length=1)
    role: str = Field(pattern=ROLE_PATTERN)
    access_level: str = Field(pattern="^(full|read|none)$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(default="")
    remember_me: bool = False


class AppSettingUpdate(BaseModel):
    app_name: str | None = Field(default=None, min_length=1)
    app_subtitle: str | None = Field(default=None)
    logo_base64: str | None = None
    favicon_base64: str | None = None
    finance_can_unlock_customer: bool | None = None


class AppSettingOut(BaseModel):
    id: int
    app_name: str
    app_subtitle: str
    logo_base64: str | None = None
    favicon_base64: str | None = None
    finance_can_unlock_customer: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


AuthUserOut.model_rebuild()



class TollDataExportGolongan(BaseModel):
    id: int
    name: str
    code: str
    description: str | None = None
    sort_order: int
    is_active: bool

class TollDataExportSection(BaseModel):
    id: int
    network: str | None = None
    name: str
    origin_name: str | None = None
    destination_name: str | None = None
    length_km: float
    gol23: float = 0
    gol45: float = 0
    sort_order: int
    is_active: bool

class TollDataExportSectionRate(BaseModel):
    section_id: int
    golongan_id: int
    rate: float

class TollDataExportGate(BaseModel):
    id: int
    section_id: int
    code: str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    sort_order: int
    is_active: bool

class TollDataExportGateFare(BaseModel):
    entry_gate_id: int
    exit_gate_id: int
    golongan_id: int
    rate: float

class TollDataExport(BaseModel):
    golongan: list[TollDataExportGolongan]
    sections: list[TollDataExportSection]
    section_rates: list[TollDataExportSectionRate]
    gates: list[TollDataExportGate]
    gate_fares: list[TollDataExportGateFare]
