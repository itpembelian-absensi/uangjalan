from app.db import SessionLocal
from app.api import update_customer
from app.schemas import CustomerCreate, CustomerTariffItem

def test_update():
    with SessionLocal() as db:
        payload = CustomerCreate(
            code="AD010",
            name="KIAN JAYA, CV",
            address="Jakarta",
            kelurahan="",
            kecamatan="",
            city="-",
            phone="",
            email="",
            is_active=True,
            force_toll=False,
            latitude=None,
            longitude=None,
            tariffs=[]
        )
        try:
            update_customer(4599, payload, db) # Assuming 4599 is AD010 id from earlier
            print("Update successful")
        except Exception as e:
            print("Update failed:", e)

if __name__ == "__main__":
    test_update()
