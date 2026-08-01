from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.roles import ROLE_LABELS, Role
from app.models import AppMenu, RoleMenuAccess

ACCESS_LEVELS = ("full", "read", "none")

ACCESS_LABELS = {
    "full": "Lihat & Edit",
    "read": "Lihat saja",
    "none": "Tidak ada akses",
}

# Admin tidak boleh kehilangan akses penuh ke menu ini
PROTECTED_ADMIN_MENUS: dict[str, str] = {
    "users": "full",
    "access_matrix": "full",
    "customer_finance_lock": "full",
}

# Muncul di Matriks Akses, tidak ditampilkan di menu navigasi samping
NAV_HIDDEN_MENU_IDS: frozenset[str] = frozenset({"customer_finance_lock"})

# Permission tulis untuk kunci/buka Kunci Finance Master Customer
CUSTOMER_FINANCE_LOCK_PERMISSION = "customers:finance_lock"


@dataclass(frozen=True)
class MenuDef:
    id: str
    label: str
    path: str
    section: str
    icon: str
    sort_order: int
    read_permission: str
    write_permission: str | None = None


DEFAULT_MENUS: list[MenuDef] = [
    MenuDef("dashboard", "Dashboard", "/", "Utama", "LayoutDashboard", 1, "dashboard:read"),
    MenuDef("delivery_routes", "Rute Pengiriman", "/delivery-routes", "Transaksi", "MapPinned", 20, "delivery_routes:read", "delivery_routes:write"),
    MenuDef("delivery_routes_report", "Laporan Rute", "/delivery-routes/report", "Transaksi", "FileBarChart", 22, "delivery_routes:read"),
    MenuDef("sales", "Uang Jalan", "/sales", "Transaksi", "Wallet", 21, "sales:read", "sales:write"),
    MenuDef("reports", "Laporan", "/reports", "Analitik", "BarChart3", 30, "reports:read", "reports:write"),
    MenuDef("customers", "Customers", "/customers", "Master Data", "Users", 31, "customers:read", "customers:write"),
    MenuDef(
        "customer_finance_lock",
        "Kunci Finance Customer",
        "/customers#finance-lock",
        "Master Data",
        "Lock",
        32,
        "customers:finance_lock_read",
        CUSTOMER_FINANCE_LOCK_PERMISSION,
    ),
    MenuDef("drivers", "Drivers", "/drivers", "Master Data", "Car", 32, "drivers:read", "drivers:write"),
    MenuDef("vehicles", "Vehicles", "/vehicles", "Master Data", "Truck", 33, "vehicles:read", "vehicles:write"),
    MenuDef("vehicle_brands", "Merek", "/vehicle-brands", "Master Data", "Minus", 34, "vehicle_brands:read", "vehicle_brands:write"),
    MenuDef("vehicle_types", "Jenis Kendaraan", "/vehicle-types", "Master Data", "Minus", 35, "vehicle_types:read", "vehicle_types:write"),
    MenuDef("bbm", "Master BBM", "/bbm", "Master Data", "Minus", 36, "bbm:read", "bbm:write"),
    MenuDef("toll_golongan", "Golongan Tol", "/toll-golongan", "Master Data", "Minus", 37, "toll:read", "toll:write"),
    MenuDef("toll_gates", "Gerbang Tol", "/toll-gates", "Master Data", "Minus", 38, "toll:read", "toll:write"),
    MenuDef("master_uang_mel", "Master Uang Mel", "/uang-mel", "Master Data", "Minus", 39, "uang_mel:read", "uang_mel:write"),
    MenuDef("master_uang_pelabuhan", "Master Uang Pelabuhan", "/uang-pelabuhan", "Master Data", "Minus", 40, "uang_pelabuhan:read", "uang_pelabuhan:write"),
    MenuDef("master_pjr", "Master PJR", "/master-pjr", "Master Data", "Minus", 41, "route_fee_pjr:read", "route_fee_pjr:write"),
    MenuDef("master_forklift_bongkaran", "Master Forklift Bongkaran", "/master-forklift-bongkaran", "Master Data", "Minus", 42, "route_fee_forklift:read", "route_fee_forklift:write"),
    MenuDef("master_parkir_liar", "Master Parkir Liar", "/master-parkir-liar", "Master Data", "Minus", 43, "route_fee_parkir_liar:read", "route_fee_parkir_liar:write"),
    MenuDef("master_parkir_kawasan", "Master Parkir Kawasan", "/master-parkir-kawasan", "Master Data", "Minus", 44, "route_fee_parkir_kawasan:read", "route_fee_parkir_kawasan:write"),
    MenuDef("warehouse", "Gudang", "/warehouse", "Master Data", "Warehouse", 45, "warehouse:read", "warehouse:write"),
    MenuDef("toll_sections", "Ruas Tol", "/toll-sections", "Master Data", "Route", 46, "toll:read", "toll:write"),
    MenuDef("users", "Manajemen User", "/users", "Administrasi", "Shield", 47, "users:read", "users:write"),
    MenuDef("access_matrix", "Matriks Akses", "/access-matrix", "Administrasi", "Table2", 48, "access_matrix:read", "access_matrix:write"),
    MenuDef("app_settings", "Pengaturan Aplikasi", "/app-settings", "Administrasi", "Settings", 49, "app_settings:read", "app_settings:write"),
]


def _default_access_level(menu: MenuDef, role: Role) -> str:
    """Hitung akses default dari definisi awal (sebelum ada DB)."""
    defaults: dict[str, dict[Role, str]] = {
        "dashboard": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "read", Role.GUDANG: "read"},
        "customers": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        # full = boleh kunci & buka Kunci Finance; read = lihat status saja; none = tidak boleh ubah
        "customer_finance_lock": {
            Role.ADMIN: "full",
            Role.FINANCE: "full",
            Role.MARKETING: "none",
            Role.GUDANG: "none",
        },
        "drivers": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "full", Role.GUDANG: "read"},
        "vehicles": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "full", Role.GUDANG: "read"},
        "vehicle_brands": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "vehicle_types": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "master_uang_mel": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "master_uang_pelabuhan": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "master_pjr": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "master_forklift_bongkaran": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "master_parkir_liar": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "master_parkir_kawasan": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "read"},
        "warehouse": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "full", Role.GUDANG: "full"},
        "bbm": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "none"},
        "toll_golongan": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "none"},
        "toll_gates": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "full", Role.GUDANG: "none"},
        "toll_sections": {Role.ADMIN: "full", Role.FINANCE: "none", Role.MARKETING: "full", Role.GUDANG: "none"},
        "delivery_routes": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "full", Role.GUDANG: "read"},
        # Samakan dengan akses lihat rute — dipakai tab Laporan Rute
        "delivery_routes_report": {
            Role.ADMIN: "full",
            Role.FINANCE: "full",
            Role.MARKETING: "read",
            Role.GUDANG: "read",
        },
        "sales": {Role.ADMIN: "full", Role.FINANCE: "full", Role.MARKETING: "none", Role.GUDANG: "full"},
        # Finance = Admin untuk halaman Laporan (lihat + export)
        "reports": {
            Role.ADMIN: "full",
            Role.FINANCE: "full",
            Role.MARKETING: "read",
            Role.GUDANG: "read",
        },
        "users": {Role.ADMIN: "full", Role.FINANCE: "none", Role.MARKETING: "none", Role.GUDANG: "none"},
        "access_matrix": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "read", Role.GUDANG: "none"},
        "app_settings": {Role.ADMIN: "full", Role.FINANCE: "read", Role.MARKETING: "read", Role.GUDANG: "read"},
    }
    return defaults.get(menu.id, {}).get(role, "none")


_PERMISSIONS_CACHE: dict[str, set[Role]] = {}


def get_permissions_cache() -> dict[str, set[Role]]:
    return _PERMISSIONS_CACHE


def reload_permissions_cache(db: Session) -> None:
    global _PERMISSIONS_CACHE
    menus = _load_menus(db)
    rows = db.scalars(select(RoleMenuAccess)).all()
    access_map = {(r.menu_id, r.role): r.access_level for r in rows}

    perms: dict[str, set[Role]] = {}
    for menu in menus:
        for role in Role:
            level = access_map.get((menu.id, role.value), "none")
            _apply_level_to_permissions(perms, menu, role, level)

    _PERMISSIONS_CACHE = perms


def _apply_level_to_permissions(
    perms: dict[str, set[Role]],
    menu: AppMenu | MenuDef,
    role: Role,
    level: str,
) -> None:
    if level in ("read", "full"):
        perms.setdefault(menu.read_permission, set()).add(role)
    if level == "full" and menu.write_permission:
        perms.setdefault(menu.write_permission, set()).add(role)


def has_permission(role: str, permission: str) -> bool:
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    allowed = _PERMISSIONS_CACHE.get(permission, set())
    return role_enum in allowed


def permissions_for_role(role: str) -> list[str]:
    try:
        role_enum = Role(role)
    except ValueError:
        return []
    return sorted(p for p, roles in _PERMISSIONS_CACHE.items() if role_enum in roles)


def _load_menus(db: Session) -> list[AppMenu]:
    return list(
        db.scalars(select(AppMenu).order_by(AppMenu.sort_order.asc(), AppMenu.id.asc())).all()
    )


def seed_menus_and_access(db: Session) -> None:
    existing = db.scalar(select(AppMenu.id).limit(1))
    if existing:
        return

    for m in DEFAULT_MENUS:
        db.add(
            AppMenu(
                id=m.id,
                label=m.label,
                path=m.path,
                section=m.section,
                icon=m.icon,
                sort_order=m.sort_order,
                read_permission=m.read_permission,
                write_permission=m.write_permission,
            )
        )
    db.flush()

    for m in DEFAULT_MENUS:
        for role in Role:
            level = _default_access_level(m, role)
            db.add(RoleMenuAccess(menu_id=m.id, role=role.value, access_level=level))
    db.commit()


def sync_menu_definitions(db: Session) -> None:
    """Selaraskan label/path/urutan menu dengan DEFAULT_MENUS (untuk DB yang sudah ada)."""
    for m in DEFAULT_MENUS:
        row = db.get(AppMenu, m.id)
        if row:
            row.label = m.label
            row.path = m.path
            row.section = m.section
            row.icon = m.icon
            row.sort_order = m.sort_order
            row.read_permission = m.read_permission
            row.write_permission = m.write_permission
        else:
            db.add(
                AppMenu(
                    id=m.id,
                    label=m.label,
                    path=m.path,
                    section=m.section,
                    icon=m.icon,
                    sort_order=m.sort_order,
                    read_permission=m.read_permission,
                    write_permission=m.write_permission,
                )
            )
            for role in Role:
                db.add(
                    RoleMenuAccess(
                        menu_id=m.id,
                        role=role.value,
                        access_level=_default_access_level(m, role),
                    )
                )
    db.commit()


def sync_role_access(db: Session) -> None:
    """Tambahkan baris akses menu untuk role baru pada database yang sudah ada."""
    menus = _load_menus(db)
    if not menus:
        return
    menu_defs = {m.id: m for m in DEFAULT_MENUS}
    existing = {
        (r.menu_id, r.role) for r in db.scalars(select(RoleMenuAccess)).all()
    }
    added = False
    for menu in menus:
        menu_def = menu_defs.get(menu.id)
        for role in Role:
            key = (menu.id, role.value)
            if key in existing:
                continue
            level = _default_access_level(menu_def, role) if menu_def else "none"
            db.add(RoleMenuAccess(menu_id=menu.id, role=role.value, access_level=level))
            added = True
    if added:
        db.commit()


def ensure_finance_reports_like_admin(db: Session) -> None:
    """Pastikan Finance punya akses Laporan (dan Laporan Rute) setara Admin."""
    changed = False
    for menu_id, level in (
        ("reports", "full"),
        ("delivery_routes_report", "full"),
    ):
        if not db.get(AppMenu, menu_id):
            continue
        row = db.scalar(
            select(RoleMenuAccess).where(
                RoleMenuAccess.menu_id == menu_id,
                RoleMenuAccess.role == Role.FINANCE.value,
            )
        )
        if row is None:
            db.add(
                RoleMenuAccess(
                    menu_id=menu_id,
                    role=Role.FINANCE.value,
                    access_level=level,
                )
            )
            changed = True
        elif row.access_level != level:
            row.access_level = level
            changed = True

        admin_row = db.scalar(
            select(RoleMenuAccess).where(
                RoleMenuAccess.menu_id == menu_id,
                RoleMenuAccess.role == Role.ADMIN.value,
            )
        )
        if admin_row is None:
            db.add(
                RoleMenuAccess(
                    menu_id=menu_id,
                    role=Role.ADMIN.value,
                    access_level=level,
                )
            )
            changed = True
        elif admin_row.access_level not in ("full", "read"):
            admin_row.access_level = level
            changed = True

    if changed:
        db.commit()


def access_matrix_payload(db: Session, *, can_edit: bool) -> dict:
    menus = _load_menus(db)
    rows = db.scalars(select(RoleMenuAccess)).all()
    access_map = {(r.menu_id, r.role): r.access_level for r in rows}

    roles = [{"id": role.value, "label": ROLE_LABELS[role]} for role in Role]
    sections: dict[str, list[dict]] = {}

    for menu in menus:
        access = {
            role.value: access_map.get((menu.id, role.value), "none") for role in Role
        }
        row = {
            "id": menu.id,
            "label": menu.label,
            "path": menu.path,
            "access": access,
        }
        sections.setdefault(menu.section, []).append(row)

    return {
        "roles": roles,
        "sections": [{"name": name, "items": items} for name, items in sections.items()],
        "legend": ACCESS_LABELS,
        "can_edit": can_edit,
        "access_levels": list(ACCESS_LEVELS),
    }


def menus_for_role(role: str, db: Session | None = None) -> list[dict]:
    if db is not None:
        menus = _load_menus(db)
        rows = db.scalars(select(RoleMenuAccess).where(RoleMenuAccess.role == role)).all()
        access_map = {r.menu_id: r.access_level for r in rows}
    else:
        menus = []
        access_map = {}

    items: list[dict] = []
    for menu in menus:
        if menu.id in NAV_HIDDEN_MENU_IDS:
            continue
        level = access_map.get(menu.id, "none")
        if level == "none":
            continue
        can_write = level == "full" and bool(menu.write_permission)
        items.append(
            {
                "id": menu.id,
                "label": menu.label,
                "path": menu.path,
                "section": menu.section,
                "icon": menu.icon,
                "can_write": can_write,
                "access": level if level != "none" else "read",
            }
        )
    return items


def update_access_cell(db: Session, menu_id: str, role: str, access_level: str) -> dict:
    if access_level not in ACCESS_LEVELS:
        raise HTTPException(status_code=400, detail="Level akses tidak valid")

    try:
        Role(role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Role tidak valid")

    menu = db.get(AppMenu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu tidak ditemukan")

    if role == Role.ADMIN.value and menu_id in PROTECTED_ADMIN_MENUS:
        required = PROTECTED_ADMIN_MENUS[menu_id]
        if access_level != required:
            raise HTTPException(
                status_code=400,
                detail=f"Admin harus tetap memiliki akses '{ACCESS_LABELS[required]}' pada menu ini",
            )

    row = db.scalar(
        select(RoleMenuAccess).where(
            RoleMenuAccess.menu_id == menu_id,
            RoleMenuAccess.role == role,
        )
    )
    if row:
        row.access_level = access_level
    else:
        db.add(RoleMenuAccess(menu_id=menu_id, role=role, access_level=access_level))

    db.commit()
    reload_permissions_cache(db)
    return access_matrix_payload(db, can_edit=True)
