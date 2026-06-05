from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
engine = create_engine(os.environ["DATABASE_URL"])

with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE customers ADD COLUMN kelurahan TEXT;"))
    except Exception as e:
        print("customers.kelurahan:", e)
    
    try:
        conn.execute(text("ALTER TABLE customers ADD COLUMN kecamatan TEXT;"))
    except Exception as e:
        print("customers.kecamatan:", e)

    try:
        conn.execute(text("ALTER TABLE warehouse_settings ADD COLUMN kelurahan TEXT;"))
    except Exception as e:
        print("warehouse_settings.kelurahan:", e)

    try:
        conn.execute(text("ALTER TABLE warehouse_settings ADD COLUMN kecamatan TEXT;"))
    except Exception as e:
        print("warehouse_settings.kecamatan:", e)

print("Migration completed.")
