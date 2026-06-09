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
    tariffs: list[CustomerTariffOut] = Field(default_factory=list)
    created_at: datetime

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


class VehicleTypeCreate(BaseModel):
    name: str = Field(min_length=1)
    toll_golongan_id: int | None = None
    bbm_id: int | None = None
    km_per_liter: float | None = Field(default=None, gt=0)
    uang_mel: float = Field(ge=0, default=0)


class VehicleTypeOut(BaseModel):
    id: int
    name: str
    toll_golongan_id: int | None = None
    toll_golongan_name: str | None = None
    toll_golongan_code: str | None = None
    bbm_id: int | None = None
    bbm_name: str | None = None
    bbm_price: float | None = None
    km_per_liter: float | None = None
    uang_mel: float = 0
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
    stops: list[DeliveryRouteStopOut] = Field(default_factory=list)
    sale_id: int | None = None
    sale_no: str | None = None
    sale_vehicle_plate: str | None = None
    sale_driver_name: str | None = None
    is_finance_paid: bool = False
    finance_paid_at: datetime | None = None
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
    details: list[SaleDetailOut] = Field(default_factory=list)
    is_finance_paid: bool = False
    finance_paid_at: datetime | None = None
    finance_paid_by_name: str | None = None
    created_at: datetime

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


class RouteProcessOut(BaseModel):
    customer_id: int | None = None
    customer_name: str
    origin: RoutePoint
    destination: RoutePoint
    distance_km: float
    duration_min: float
    toll_idr: float
    toll_is_estimate: bool
    toll_note: str | None = None
    toll_by_vehicle: list[VehicleTollEstimate] = Field(default_factory=list)
    geometry: list[list[float]] = Field(default_factory=list)


class GeocodeRequest(BaseModel):
    address: str | None = None
    kelurahan: str | None = None
    kecamatan: str | None = None
    city: str | None = None
    name: str | None = None


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
    name: str
    length_km: float
    sort_order: int
    is_active: bool
    rates: list[TollSectionRateOut] = Field(default_factory=list)


class TollSectionCreate(BaseModel):
    name: str = Field(min_length=1)
    length_km: float = Field(gt=0)
    sort_order: int = 0
    is_active: bool = True
    rates: list[TollSectionRateItem] = Field(default_factory=list)


class TollSectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    length_km: float | None = Field(default=None, gt=0)
    sort_order: int | None = None
    is_active: bool | None = None
    rates: list[TollSectionRateItem] | None = None


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


class AppSettingOut(BaseModel):
    id: int
    app_name: str
    app_subtitle: str
    logo_base64: str | None = None
    favicon_base64: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


AuthUserOut.model_rebuild()
