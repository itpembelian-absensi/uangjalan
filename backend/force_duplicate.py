from app.db import SessionLocal
from app.models import Customer
from sqlalchemy.exc import IntegrityError

def force_duplicate():
    with SessionLocal() as db:
        try:
            # AD010 exists. Let's try to create another one.
            db.add(Customer(
                code="AD010",
                name="Duplicate Code",
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            print("Error type:", type(e))
            print("Error msg:", str(e))

if __name__ == "__main__":
    force_duplicate()
