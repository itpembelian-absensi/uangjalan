from __future__ import annotations

from sqlalchemy.orm import Session

from app.permissions_service import (
    ACCESS_LABELS,
    access_matrix_payload,
    menus_for_role,
)

__all__ = ["ACCESS_LABELS", "access_matrix", "menus_for_role"]


def access_matrix(db: Session, *, can_edit: bool = False) -> dict:
    return access_matrix_payload(db, can_edit=can_edit)
