from app.db import engine, SessionLocal
from app.api import _replace_customer_tariffs
from app.models import Customer
from app.schemas import CustomerTariffItem
from sqlalchemy import select

def reproduce():
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.code == 'AD010'))
        if not customer:
            print("Customer AD010 not found")
            return
        
        print(f"Customer id: {customer.id}")
        # Fetch current tariffs
        current_tariffs = customer.tariffs
        tariffs = []
        for t in current_tariffs:
            tariffs.append(CustomerTariffItem(
                vehicle_type_id=t.vehicle_type_id,
                uang_jalan=t.uang_jalan,
                bbm=t.bbm,
                tol=t.tol,
                uang_mel=t.uang_mel,
                parkir=t.parkir,
                lain_lain=t.lain_lain
            ))
        
        if not tariffs:
            print("No tariffs found to test.")
        
        try:
            _replace_customer_tariffs(db, customer.id, tariffs)
            db.commit()
            print("Commit successful!")
        except Exception as e:
            db.rollback()
            print(f"Error during commit: {type(e).__name__}: {e}")

if __name__ == '__main__':
    reproduce()
