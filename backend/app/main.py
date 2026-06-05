from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.api import router as api_router
from app.auth_routes import router as auth_router, users_router
from app.core.config import settings
from app.db import ensure_schema
from app.ui import auth_router as ui_auth_router
from app.ui import router as ui_router


def _friendly_db_message(exc: SQLAlchemyError) -> str:
    msg = str(exc)
    if isinstance(exc, IntegrityError):
        lower = msg.lower()
        if "delivery_route_stops" in lower or "delivery_routes" in lower:
            return (
                "Customer tidak bisa dihapus karena masih dipakai di rute pengiriman. "
                "Hapus dari rute atau hapus rute tersebut terlebih dahulu."
            )
        if "sale_details" in lower or "sales" in lower:
            return (
                "Customer tidak bisa dihapus karena masih dipakai di transaksi uang jalan. "
                "Hapus transaksi tersebut terlebih dahulu."
            )
        if "cash_disbursements" in lower:
            return (
                "Customer tidak bisa dihapus karena masih dipakai di pengeluaran kas. "
                "Hapus data tersebut terlebih dahulu."
            )
        if "foreign key" in lower or "violates" in lower:
            return "Data tidak bisa dihapus karena masih dipakai di transaksi lain."
    if "28P01" in msg or "password authentication failed" in msg.lower():
        return (
            "Password PostgreSQL salah. Edit DATABASE_URL di backend/.env "
            "(ganti password setelah postgres:), lalu restart npm run dev."
        )
    if 'database "uang_pengiriman" does not exist' in msg.lower():
        return 'Database "uang_pengiriman" belum dibuat. Jalankan CREATE DATABASE di pgAdmin.'
    return "Koneksi atau query database gagal. Periksa PostgreSQL dan file backend/.env."


def create_app() -> FastAPI:
    ensure_schema()
    app = FastAPI(title=settings.app_name)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(_request: Request, exc: SQLAlchemyError):
        status_code = 409 if isinstance(exc, IntegrityError) else 503
        return JSONResponse(
            status_code=status_code,
            content={"detail": _friendly_db_message(exc)},
        )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=False,
        max_age=30 * 24 * 60 * 60,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/ui")

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(api_router)
    app.include_router(ui_auth_router)
    app.include_router(ui_router)

    if settings.enable_db_tools:
        from app.db_tools import router as db_tools_router
        app.include_router(db_tools_router)

    return app


app = create_app()

