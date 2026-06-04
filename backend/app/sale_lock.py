from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Sale

MSG_ROUTE_SALE_EXISTS = (
    "Rute tidak dapat diubah selama uang jalan masih ada. "
    "Hapus uang jalan terlebih dahulu."
)
MSG_ROUTE_FINANCE_PAID = (
    "Rute dikunci karena uang jalan sudah disetujui dibayar oleh Finance. "
    "Hapus transaksi uang jalan di menu Uang Jalan untuk membuka kunci."
)
MSG_SALE_FINANCE_PAID = (
    "Transaksi uang jalan sudah disetujui dibayar dan tidak dapat diubah. "
    "Hapus transaksi untuk membuka kunci rute."
)


def sale_finance_locked(sale: Sale | None) -> bool:
    return sale is not None and sale.finance_paid_at is not None


def route_sale(db: Session, route_id: int) -> Sale | None:
    return db.scalar(select(Sale).where(Sale.delivery_route_id == route_id))


def assert_route_editable(db: Session, route_id: int) -> None:
    sale = route_sale(db, route_id)
    if sale_finance_locked(sale):
        raise HTTPException(status_code=400, detail=MSG_ROUTE_FINANCE_PAID)


def assert_sale_editable(sale: Sale) -> None:
    if sale_finance_locked(sale):
        raise HTTPException(status_code=400, detail=MSG_SALE_FINANCE_PAID)
