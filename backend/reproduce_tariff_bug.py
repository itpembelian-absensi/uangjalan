from app.db import engine, SessionLocal
from app.api import _replace_customer_tariffs
from app.models import Customer, CustomerVehicleTariff, VehicleType
from app.schemas import CustomerTariffItem
from sqlalchemy import select

def reproduce():
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.code == 'AD010'))
        if not customer:
            print("Customer AD010 not found")
            return
            
        vehicle_type = db.scalars(select(VehicleType).limit(1)).first()
        if not vehicle_type:
            print("No vehicle type found")
            return
            
        print("Inserting initial tariffs...")
        db.add(CustomerVehicleTariff(
            customer_id=customer.id,
            vehicle_type_id=vehicle_type.id,
            uang_jalan=100000,
            bbm=0, tol=0, uang_mel=0, parkir=0, lain_lain=0
        ))
        db.commit()
        
        print("Attempting to replace tariffs...")
        tariffs = [CustomerTariffItem(
            vehicle_type_id=vehicle_type.id,
            uang_jalan=200000,
            bbm=0, tol=0, uang_mel=0, parkir=0, lain_lain=0
        )]
        try:
            _replace_customer_tariffs(db, customer.id, tariffs)
            db.commit()
            print("Replace successful!")
        except Exception as e:
            db.rollback()
            print(f"Error during commit: {type(e).__name__}: {e}")

if __name__ == '__main__':
    reproduce()
