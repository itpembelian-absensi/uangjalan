import sys
import os

# Add the backend directory to sys.path so we can import app
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)

from app.db import SessionLocal
from app.bpjt_import_service import _renumber_sort_orders

def fix_sort_orders():
    db = SessionLocal()
    try:
        _renumber_sort_orders(db)
        db.commit()
        print("Berhasil memperbaiki nomor urut (sort_order) untuk semua ruas tol.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_sort_orders()
