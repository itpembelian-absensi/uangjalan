"""Contoh data awal. Jalankan dari folder backend setelah schema.sql."""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    CashDisbursement,
    Customer,
    CustomerVehicleTariff,
    Driver,
    Vehicle,
    VehicleBrand,
    VehicleType,
)


def main() -> None:
    db = SessionLocal()
    try:
        if db.scalars(select(Customer).limit(1)).first():
            print("Data sudah ada, seed dilewati.")
            return

        c1 = Customer(name="PT Maju Jaya")
        c2 = Customer(name="CV Sumber Rejeki")
        b1 = VehicleBrand(name="Isuzu")
        b2 = VehicleBrand(name="Mitsubishi")
        t1 = VehicleType(name="Fuso")
        t2 = VehicleType(name="Tronton")
        db.add_all([c1, c2, b1, b2, t1, t2])
        db.flush()

        db.add_all(
            [
                CustomerVehicleTariff(
                    customer_id=c1.id, vehicle_type_id=t1.id, uang_jalan=100000, tambahan_uang_jalan=0
                ),
                CustomerVehicleTariff(
                    customer_id=c2.id, vehicle_type_id=t2.id, uang_jalan=150000, tambahan_uang_jalan=25000
                ),
            ]
        )

        v1 = Vehicle(plate_number="B 1234 ABC", brand_id=b1.id)
        v2 = Vehicle(plate_number="B 5678 XYZ", brand_id=b2.id)
        d1 = Driver(name="Budi Santoso", phone="081234567890")
        d2 = Driver(name="Andi Wijaya", phone="081298765432")
        db.add_all([v1, v2, d1, d2])
        db.flush()

        db.add_all(
            [
                CashDisbursement(
                    customer_id=c1.id,
                    vehicle_type_id=t1.id,
                    amount=100000,
                    description="Uang jalan",
                ),
                CashDisbursement(
                    customer_id=c2.id,
                    vehicle_type_id=t2.id,
                    amount=175000,
                    description="Uang jalan",
                ),
            ]
        )
        db.commit()
        print("Seed selesai: 2 customer, 2 kendaraan, 2 supir, 2 pengeluaran.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
