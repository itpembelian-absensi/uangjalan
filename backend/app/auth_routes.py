from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    login_user,
    logout_user,
    require_authenticated,
    require_permission,
)
from app.db import get_db
from app.menu_access import access_matrix
from app.models import User
from app.permissions_service import (
    has_permission,
    menus_for_role,
    permissions_for_role,
    update_access_cell,
)
from app.roles import ROLE_LABELS, Role
from app.schemas import (
    AccessMatrixCellUpdate,
    AccessMatrixOut,
    AuthUserOut,
    LoginRequest,
    MenuAccessOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        role_label=ROLE_LABELS.get(Role(user.role), user.role),
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _auth_user_out(user: User, db: Session) -> AuthUserOut:
    return AuthUserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        role_label=ROLE_LABELS.get(Role(user.role), user.role),
        permissions=permissions_for_role(user.role),
        menus=[MenuAccessOut(**m) for m in menus_for_role(user.role, db)],
    )


@router.post("/login", response_model=AuthUserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    if not payload.password:
        raise HTTPException(
            status_code=400,
            detail="Password wajib diisi. Matikan Auto Login jika session sudah berakhir.",
        )
    user = db.scalar(select(User).where(User.username == username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    login_user(request, user, remember_me=payload.remember_me)
    return _auth_user_out(user, db)


@router.post("/logout")
def logout(request: Request):
    logout_user(request)
    return {"ok": True}


@router.get("/me", response_model=AuthUserOut)
def me(user: User = Depends(require_authenticated), db: Session = Depends(get_db)):
    return _auth_user_out(user, db)


@router.get("/access-matrix", response_model=AccessMatrixOut)
def get_access_matrix(
    db: Session = Depends(get_db),
    user: User = Depends(require_authenticated),
):
    can_edit = has_permission(user.role, "access_matrix:write")
    return access_matrix(db, can_edit=can_edit)


@router.put("/access-matrix", response_model=AccessMatrixOut)
def put_access_matrix(
    payload: AccessMatrixCellUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("access_matrix:write")),
):
    return update_access_cell(db, payload.menu_id, payload.role, payload.access_level)


users_router = APIRouter(prefix="/api/users", tags=["users"])


@users_router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    rows = db.scalars(select(User).order_by(User.username.asc())).all()
    return [_user_out(u) for u in rows]


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:write")),
):
    username = payload.username.strip().lower()
    if db.scalar(select(User.id).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Username sudah digunakan")
    obj = User(
        username=username,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _user_out(obj)


@users_router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("users:write")),
):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if obj.id == current.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Tidak dapat menonaktifkan akun sendiri")
    if payload.full_name is not None:
        obj.full_name = payload.full_name.strip()
    if payload.role is not None:
        if obj.id == current.id and payload.role != current.role:
            raise HTTPException(status_code=400, detail="Tidak dapat mengubah role akun sendiri")
        obj.role = payload.role
    if payload.is_active is not None:
        obj.is_active = payload.is_active
    if payload.password:
        obj.password_hash = hash_password(payload.password)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _user_out(obj)


@users_router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("users:write")),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun sendiri")
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    db.delete(obj)
    db.commit()
