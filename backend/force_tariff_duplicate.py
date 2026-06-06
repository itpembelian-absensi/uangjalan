from app.db import SessionLocal
from app.models import CustomerVehicleTariff

def force_tariff_duplicate():
    with SessionLocal() as db:
        try:
            # Insert two identical tariffs for same customer and vehicle type
            db.add(CustomerVehicleTariff(
                customer_id=4599,
                vehicle_type_id=1,
                uang_jalan=1000
            ))
            db.add(CustomerVehicleTariff(
                customer_id=4599,
                vehicle_type_id=1,
                uang_jalan=2000
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            print("Error type:", type(e))
            print("Error msg:", str(e))

if __name__ == "__main__":
    force_tariff_duplicate()
