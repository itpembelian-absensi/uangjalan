import threading
from app.db import SessionLocal
from app.api import update_customer
from app.schemas import CustomerCreate, CustomerTariffItem

payload = CustomerCreate(
    code="AD010",
    name="Concurrent Test",
    tariffs=[CustomerTariffItem(
        vehicle_type_id=1,
        uang_jalan=1000,
        bbm=0, tol=0, uang_mel=0, parkir=0, lain_lain=0
    )]
)

def run_update():
    with SessionLocal() as db:
        try:
            update_customer(4599, payload, db)
            print("Success")
        except Exception as e:
            print("Failed:", type(e), str(e))

def test_concurrent():
    t1 = threading.Thread(target=run_update)
    t2 = threading.Thread(target=run_update)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

if __name__ == "__main__":
    test_concurrent()
