from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    FINANCE = "finance"
    MARKETING = "marketing"
    GUDANG = "gudang"


ROLE_LABELS = {
    Role.ADMIN: "Admin",
    Role.FINANCE: "Finance & Accounting",
    Role.MARKETING: "Marketing",
    Role.GUDANG: "Gudang",
}

ROLE_PATTERN = r"^(admin|finance|marketing|gudang)$"
