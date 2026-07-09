from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.permissions_service import has_permission, permissions_for_role
from app.roles import ROLE_LABELS, Role

PATH_RESOURCE_MAP: list[tuple[str, str]] = [
    ("/api/auth/access-matrix", "access_matrix"),
    ("/api/customers", "customers"),
    ("/api/vehicle-brands", "vehicle_brands"),
    ("/api/bbm", "bbm"),
    ("/api/uang-mel", "uang_mel"),
    ("/api/uang-pelabuhan", "uang_pelabuhan"),
    ("/api/route-fees/pjr", "route_fee_pjr"),
    ("/api/route-fees/forklift_bongkaran", "route_fee_forklift"),
    ("/api/route-fees/parkir_liar", "route_fee_parkir_liar"),
    ("/api/route-fees/parkir_kawasan", "route_fee_parkir_kawasan"),
    ("/api/vehicle-types", "vehicle_types"),
    ("/api/vehicles", "vehicles"),
    ("/api/drivers", "drivers"),
    ("/api/cash-disbursements", "sales"),
    ("/api/reports", "reports"),
    ("/api/sales", "sales"),
    ("/api/delivery-routes", "delivery_routes"),
    ("/api/warehouse", "warehouse"),
    ("/api/routing", "delivery_routes"),
    ("/api/toll-golongan", "toll"),
    ("/api/toll-sections", "toll"),
    ("/api/geocode", "customers"),
    ("/api/users", "users"),
]

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

SESSION_TTL_SECONDS = 8 * 60 * 60
REMEMBER_TTL_SECONDS = 30 * 24 * 60 * 60


def _session_valid(request: Request) -> bool:
    expires_at = request.session.get("expires_at")
    if expires_at is None:
        return bool(request.session.get("user_id"))
    try:
        return float(expires_at) > time.time()
    except (TypeError, ValueError):
        return False


def can_generate_sale_from_route(role: str) -> bool:
    return has_permission(role, "sales:write") or has_permission(role, "delivery_routes:write")


def resolve_api_permission(path: str, method: str) -> str | None:
    if ("/generate-sale" in path or "/sync-sales" in path) and method in WRITE_METHODS:
        return None
    for prefix, resource in PATH_RESOURCE_MAP:
        if path == prefix or path.startswith(f"{prefix}/"):
            action = "write" if method in WRITE_METHODS else "read"
            return f"{resource}:{action}"
    return None


def _session_user_id(request: Request) -> int | None:
    raw = request.session.get("user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def get_current_user(request: Request, db: Session) -> User | None:
    if not _session_valid(request):
        logout_user(request)
        return None
    user_id = _session_user_id(request)
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def login_user(request: Request, user: User, *, remember_me: bool = False) -> None:
    request.session.clear()
    now = time.time()
    ttl = REMEMBER_TTL_SECONDS if remember_me else SESSION_TTL_SECONDS
    request.session["user_id"] = user.id
    request.session["logged_in"] = True
    request.session["role"] = user.role
    request.session["remember_me"] = remember_me
    request.session["expires_at"] = now + ttl


def logout_user(request: Request) -> None:
    request.session.clear()


def require_authenticated(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu")
    return user


def require_api_access(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user = require_authenticated(request, db)
    path = request.url.path
    method = request.method
    if ("/generate-sale" in path or "/sync-sales" in path) and method in WRITE_METHODS:
        if not can_generate_sale_from_route(user.role):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini")
        return user
    permission = resolve_api_permission(path, method)
    if permission and not has_permission(user.role, permission):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini")
    return user


def require_permission(permission: str):
    def _checker(
        request: Request,
        db: Session = Depends(get_db),
    ) -> User:
        user = require_authenticated(request, db)
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke fitur ini")
        return user

    return _checker


CurrentUser = Annotated[User, Depends(require_authenticated)]
ApiUser = Annotated[User, Depends(require_api_access)]
