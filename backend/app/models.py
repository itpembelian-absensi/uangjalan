from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, server_default="marketing")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AppMenu(Base):
    __tablename__ = "app_menus"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    section: Mapped[str] = mapped_column(String, nullable=False)
    icon: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    read_permission: Mapped[str] = mapped_column(String, nullable=False)
    write_permission: Mapped[str | None] = mapped_column(String, nullable=True)


class RoleMenuAccess(Base):
    __tablename__ = "role_menu_access"

    menu_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_menus.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, primary_key=True)
    access_level: Mapped[str] = mapped_column(String, nullable=False)

    menu: Mapped[AppMenu] = relationship()


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    kelurahan: Mapped[str | None] = mapped_column(String, nullable=True)
    kecamatan: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    force_toll: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tariffs: Mapped[list["CustomerVehicleTariff"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class WarehouseSetting(Base):
    __tablename__ = "warehouse_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, server_default="Gudang Utama")
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    kelurahan: Mapped[str | None] = mapped_column(String, nullable=True)
    kecamatan: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_name: Mapped[str] = mapped_column(String, nullable=False, server_default="Biaya Pengiriman")
    app_subtitle: Mapped[str] = mapped_column(String, nullable=False, server_default="Premium Logistics")
    logo_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )



class TollSection(Base):
    __tablename__ = "toll_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    length_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, server_default="1")
    gol23: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    gol45: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rates: Mapped[list["TollSectionRate"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class TollGolongan(Base):
    __tablename__ = "toll_golongan"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rates: Mapped[list["TollSectionRate"]] = relationship(back_populates="golongan")


class TollSectionRate(Base):
    __tablename__ = "toll_section_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("toll_sections.id", ondelete="CASCADE"), nullable=False
    )
    golongan_id: Mapped[int] = mapped_column(
        ForeignKey("toll_golongan.id", ondelete="CASCADE"), nullable=False
    )
    rate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    section: Mapped[TollSection] = relationship(back_populates="rates")
    golongan: Mapped[TollGolongan] = relationship(back_populates="rates")

    __table_args__ = (
        UniqueConstraint("section_id", "golongan_id", name="uq_toll_section_golongan"),
    )


class CustomerVehicleTariff(Base):
    __tablename__ = "customer_vehicle_tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle_types.id", ondelete="CASCADE"), nullable=False
    )
    uang_jalan: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    bbm: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    tol: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    uang_mel: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    parkir: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    lain_lain: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")

    customer: Mapped[Customer] = relationship(back_populates="tariffs")
    vehicle_type: Mapped["VehicleType"] = relationship()

    __table_args__ = (
        UniqueConstraint("customer_id", "vehicle_type_id", name="uq_customer_vehicle_type"),
    )


class VehicleBrand(Base):
    __tablename__ = "vehicle_brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BbmMaster(Base):
    __tablename__ = "bbm_master"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VehicleType(Base):
    __tablename__ = "vehicle_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    toll_golongan_id: Mapped[int | None] = mapped_column(
        ForeignKey("toll_golongan.id", ondelete="SET NULL"), nullable=True
    )
    bbm_id: Mapped[int | None] = mapped_column(
        ForeignKey("bbm_master.id", ondelete="SET NULL"), nullable=True
    )
    km_per_liter: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    uang_mel: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    toll_golongan: Mapped["TollGolongan | None"] = relationship()
    bbm: Mapped["BbmMaster | None"] = relationship()


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("vehicle_brands.id"), nullable=False)
    type_id: Mapped[int | None] = mapped_column(ForeignKey("vehicle_types.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped[VehicleBrand] = relationship()
    type: Mapped[VehicleType] = relationship()


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_account: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CashDisbursement(Base):
    __tablename__ = "cash_disbursements"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle_types.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    disbursed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped[Customer] = relationship()
    vehicle_type: Mapped["VehicleType | None"] = relationship()

    __table_args__ = (
        Index("idx_cash_disbursements_customer", "customer_id"),
        Index("idx_cash_disbursements_disbursed_at", "disbursed_at"),
    )


class DeliveryRoute(Base):
    __tablename__ = "delivery_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_no: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", onupdate="CASCADE"), nullable=True
    )
    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle_types.id", onupdate="CASCADE"), nullable=False
    )
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", onupdate="CASCADE"), nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    ritpiase: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vehicle: Mapped[Vehicle | None] = relationship()
    vehicle_type: Mapped["VehicleType"] = relationship()
    driver: Mapped[Driver | None] = relationship()
    stops: Mapped[list["DeliveryRouteStop"]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="DeliveryRouteStop.sort_order"
    )
    sale: Mapped["Sale | None"] = relationship(back_populates="delivery_route", uselist=False)

    __table_args__ = (
        Index("idx_delivery_routes_date", "date"),
        Index("idx_delivery_routes_vehicle", "vehicle_id"),
        Index("idx_delivery_routes_vehicle_type", "vehicle_type_id"),
    )


class DeliveryRouteStop(Base):
    __tablename__ = "delivery_route_stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_routes.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", onupdate="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    route: Mapped[DeliveryRoute] = relationship(back_populates="stops")
    customer: Mapped[Customer] = relationship()
    lines: Mapped[list["DeliveryRouteStopLine"]] = relationship(
        back_populates="stop", cascade="all, delete-orphan", order_by="DeliveryRouteStopLine.sort_order"
    )

    __table_args__ = (
        Index("idx_delivery_route_stops_route", "route_id"),
        UniqueConstraint("route_id", "customer_id", name="uq_route_customer"),
    )


class DeliveryRouteStopLine(Base):
    __tablename__ = "delivery_route_stop_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    stop_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_route_stops.id", ondelete="CASCADE"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    stop: Mapped[DeliveryRouteStop] = relationship(back_populates="lines")

    __table_args__ = (Index("idx_delivery_route_stop_lines_stop", "stop_id"),)


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_no: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", onupdate="CASCADE"), nullable=True
    )
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", onupdate="CASCADE"), nullable=True
    )
    delivery_route_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_routes.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_uang_jalan: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, server_default="0"
    )
    finance_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finance_paid_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vehicle: Mapped["Vehicle | None"] = relationship()
    finance_paid_by_user: Mapped["User | None"] = relationship(foreign_keys=[finance_paid_by])
    driver: Mapped[Driver] = relationship()
    delivery_route: Mapped["DeliveryRoute | None"] = relationship(back_populates="sale")
    details: Mapped[list["SaleDetail"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sales_date", "date"),
    )


class SaleDetail(Base):
    __tablename__ = "sale_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", onupdate="CASCADE"), nullable=False
    )
    vehicle_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle_types.id", onupdate="CASCADE"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sale: Mapped[Sale] = relationship(back_populates="details")
    customer: Mapped[Customer] = relationship()

    __table_args__ = (
        Index("idx_sale_details_sale_id", "sale_id"),
    )

