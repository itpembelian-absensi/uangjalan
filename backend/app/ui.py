from __future__ import annotations

import csv
import io
from io import BytesIO
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import login_user, logout_user
from app.db import get_db
from app.models import (
    CashDisbursement,
    Customer,
    Driver,
    User,
    Vehicle,
    VehicleBrand,
    VehicleType,
)
from app.security import verify_password
from app.reports_service import (
    customer_summary,
    disbursement_detail,
    driver_summary,
    grand_total,
)


templates = Jinja2Templates(directory="app/templates")
templates.env.filters["idr"] = lambda v: f"Rp {float(v):,.0f}".replace(",", ".")
auth_router = APIRouter(prefix="/ui", include_in_schema=False)
router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=303)


def _is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user_id"))


def require_login(request: Request):
    if request.url.path.startswith("/ui/login"):
        return
    if not _is_logged_in(request):
        raise HTTPException(status_code=303, headers={"Location": "/ui/login"})


# protect all routes on `router`
router.dependencies.append(Depends(require_login))


@auth_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )


@auth_router.post("/login")
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.username == username.strip().lower())
    )
    if user and user.is_active and verify_password(password, user.password_hash):
        login_user(request, user, remember_me=bool(remember_me))
        return _redirect("/ui")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Username atau password salah"},
        status_code=401,
    )


@auth_router.post("/logout")
def logout_action(request: Request):
    logout_user(request)
    return _redirect("/ui/login")


@router.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@router.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, db: Session = Depends(get_db)):
    items = db.scalars(select(Customer).order_by(Customer.name.asc())).all()
    return templates.TemplateResponse(
        request=request, name="customers.html", context={"items": items}
    )


@router.post("/customers")
def customers_create(name: str = Form(...), db: Session = Depends(get_db)):
    obj = Customer(name=name.strip())
    db.add(obj)
    db.commit()
    return _redirect("/ui/customers")


@router.post("/customers/{customer_id}/update")
def customers_update(customer_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    obj = db.get(Customer, customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    obj.name = name.strip()
    db.add(obj)
    db.commit()
    return _redirect("/ui/customers")


@router.post("/customers/{customer_id}/delete")
def customers_delete(customer_id: int, db: Session = Depends(get_db)):
    obj = db.get(Customer, customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    db.delete(obj)
    db.commit()
    return _redirect("/ui/customers")


@router.get("/vehicle-brands", response_class=HTMLResponse)
def vehicle_brands_page(request: Request, db: Session = Depends(get_db)):
    items = db.scalars(select(VehicleBrand).order_by(VehicleBrand.name.asc())).all()
    return templates.TemplateResponse(
        request=request, name="vehicle_brands.html", context={"items": items}
    )


@router.post("/vehicle-brands")
def vehicle_brands_create(name: str = Form(...), db: Session = Depends(get_db)):
    obj = VehicleBrand(name=name.strip())
    db.add(obj)
    db.commit()
    return _redirect("/ui/vehicle-brands")


@router.post("/vehicle-brands/{brand_id}/update")
def vehicle_brands_update(brand_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    obj = db.get(VehicleBrand, brand_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Merek tidak ditemukan")
    obj.name = name.strip()
    db.add(obj)
    db.commit()
    return _redirect("/ui/vehicle-brands")


@router.post("/vehicle-brands/{brand_id}/delete")
def vehicle_brands_delete(brand_id: int, db: Session = Depends(get_db)):
    obj = db.get(VehicleBrand, brand_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Merek tidak ditemukan")
    db.delete(obj)
    db.commit()
    return _redirect("/ui/vehicle-brands")


@router.get("/vehicle-types", response_class=HTMLResponse)
def vehicle_types_page(request: Request, db: Session = Depends(get_db)):
    items = db.scalars(select(VehicleType).order_by(VehicleType.name.asc())).all()
    return templates.TemplateResponse(
        request=request, name="vehicle_types.html", context={"items": items}
    )


@router.post("/vehicle-types")
def vehicle_types_create(name: str = Form(...), db: Session = Depends(get_db)):
    obj = VehicleType(name=name.strip())
    db.add(obj)
    db.commit()
    return _redirect("/ui/vehicle-types")


@router.post("/vehicle-types/{type_id}/update")
def vehicle_types_update(type_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    obj = db.get(VehicleType, type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Jenis tidak ditemukan")
    obj.name = name.strip()
    db.add(obj)
    db.commit()
    return _redirect("/ui/vehicle-types")


@router.post("/vehicle-types/{type_id}/delete")
def vehicle_types_delete(type_id: int, db: Session = Depends(get_db)):
    obj = db.get(VehicleType, type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Jenis tidak ditemukan")
    db.delete(obj)
    db.commit()
    return _redirect("/ui/vehicle-types")


@router.get("/vehicles", response_class=HTMLResponse)
def vehicles_page(request: Request, db: Session = Depends(get_db)):
    vehicles = db.scalars(select(Vehicle).order_by(Vehicle.plate_number.asc())).all()
    brands = db.scalars(select(VehicleBrand).order_by(VehicleBrand.name.asc())).all()
    types = db.scalars(select(VehicleType).order_by(VehicleType.name.asc())).all()
    brand_map = {b.id: b.name for b in brands}
    type_map = {t.id: t.name for t in types}
    return templates.TemplateResponse(
        request=request,
        name="vehicles.html",
        context={
            "vehicles": vehicles,
            "brands": brands,
            "types": types,
            "brand_map": brand_map,
            "type_map": type_map,
        },
    )


@router.post("/vehicles")
def vehicles_create(
    plate_number: str = Form(...),
    brand_id: int = Form(...),
    type_id: int = Form(...),
    db: Session = Depends(get_db),
):
    obj = Vehicle(
        plate_number=plate_number.strip(),
        brand_id=brand_id,
        type_id=type_id,
    )
    db.add(obj)
    db.commit()
    return _redirect("/ui/vehicles")


@router.post("/vehicles/{vehicle_id}/update")
def vehicles_update(
    vehicle_id: int,
    plate_number: str = Form(...),
    brand_id: int = Form(...),
    type_id: int = Form(...),
    db: Session = Depends(get_db),
):
    obj = db.get(Vehicle, vehicle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    obj.plate_number = plate_number.strip()
    obj.brand_id = brand_id
    obj.type_id = type_id
    db.add(obj)
    db.commit()
    return _redirect("/ui/vehicles")


@router.post("/vehicles/{vehicle_id}/delete")
def vehicles_delete(vehicle_id: int, db: Session = Depends(get_db)):
    obj = db.get(Vehicle, vehicle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    db.delete(obj)
    db.commit()
    return _redirect("/ui/vehicles")


@router.get("/drivers", response_class=HTMLResponse)
def drivers_page(request: Request, db: Session = Depends(get_db)):
    items = db.scalars(select(Driver).order_by(Driver.name.asc())).all()
    return templates.TemplateResponse(
        request=request, name="drivers.html", context={"items": items}
    )


@router.post("/drivers")
def drivers_create(
    name: str = Form(...), phone: str | None = Form(None), db: Session = Depends(get_db)
):
    obj = Driver(name=name.strip(), phone=(phone.strip() if phone else None))
    db.add(obj)
    db.commit()
    return _redirect("/ui/drivers")


@router.post("/drivers/{driver_id}/update")
def drivers_update(
    driver_id: int,
    name: str = Form(...),
    phone: str | None = Form(None),
    db: Session = Depends(get_db),
):
    obj = db.get(Driver, driver_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Supir tidak ditemukan")
    obj.name = name.strip()
    obj.phone = phone.strip() if phone else None
    db.add(obj)
    db.commit()
    return _redirect("/ui/drivers")


@router.post("/drivers/{driver_id}/delete")
def drivers_delete(driver_id: int, db: Session = Depends(get_db)):
    obj = db.get(Driver, driver_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Supir tidak ditemukan")
    db.delete(obj)
    db.commit()
    return _redirect("/ui/drivers")


@router.get("/disbursements", response_class=HTMLResponse)
def disbursements_page(
    request: Request,
    db: Session = Depends(get_db),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
):
    customers = db.scalars(select(Customer).order_by(Customer.name.asc())).all()
    types = db.scalars(select(VehicleType).order_by(VehicleType.name.asc())).all()
    details = disbursement_detail(db, from_date, to_date)
    items = [
        {
            "id": r["id"],
            "amount": r["amount"],
            "description": r["description"],
            "disbursed_at": r["disbursed_at"],
            "customer_name": r["customer_name"],
            "vehicle_type_name": r["vehicle_type_name"],
        }
        for r in details
    ]

    return templates.TemplateResponse(
        request=request,
        name="disbursements.html",
        context={
            "customers": customers,
            "types": types,
            "items": items,
            "from_date": from_date,
            "to_date": to_date,
        },
    )


def _optional_int(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


@router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    db: Session = Depends(get_db),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    driver_id: str | None = None,
    customer_id: str | None = None,
):
    driver_filter = _optional_int(driver_id)
    customer_filter = _optional_int(customer_id)
    by_driver = driver_summary(db, from_date, to_date)
    by_customer = customer_summary(db, from_date, to_date)
    details = disbursement_detail(db, from_date, to_date, customer_id=customer_filter)
    drivers = db.scalars(select(Driver).order_by(Driver.name.asc())).all()
    customers = db.scalars(select(Customer).order_by(Customer.name.asc())).all()

    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "from_date": from_date,
            "to_date": to_date,
            "driver_id": driver_filter,
            "customer_id": customer_filter,
            "by_driver": by_driver,
            "by_customer": by_customer,
            "details": details,
            "drivers": drivers,
            "customers": customers,
            "total_driver": grand_total(by_driver),
            "total_customer": grand_total(by_customer),
            "total_detail": grand_total(details),
        },
    )


@router.get("/reports/export.csv")
def reports_export_csv(
    db: Session = Depends(get_db),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    driver_id: str | None = None,
    customer_id: str | None = None,
):
    driver_filter = _optional_int(driver_id)
    customer_filter = _optional_int(customer_id)
    details = disbursement_detail(db, from_date, to_date, customer_id=customer_filter)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Tanggal", "Customer", "Jenis", "Keterangan", "Nominal"]
    )
    for r in details:
        writer.writerow(
            [
                str(r["disbursed_at"])[:10],
                r["customer_name"],
                r["vehicle_type_name"],
                r["description"] or "",
                f"{r['amount']:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["", "", "", "", "GRAND TOTAL", f"{grand_total(details):.2f}"])

    buf.seek(0)
    filename = f"laporan_{from_date or 'all'}_{to_date or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/disbursements")
def disbursements_create(
    customer_id: int = Form(...),
    vehicle_type_id: int | None = Form(None),
    amount: float = Form(...),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
):
    obj = CashDisbursement(
        customer_id=customer_id,
        vehicle_type_id=vehicle_type_id,
        amount=amount,
        description=(description.strip() if description else None),
    )
    db.add(obj)
    db.commit()
    return _redirect("/ui/disbursements")


@router.post("/disbursements/{disbursement_id}/delete")
def disbursement_delete(disbursement_id: int, db: Session = Depends(get_db)):
    obj = db.get(CashDisbursement, disbursement_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Pengeluaran tidak ditemukan")
    db.delete(obj)
    db.commit()
    return _redirect("/ui/disbursements")

