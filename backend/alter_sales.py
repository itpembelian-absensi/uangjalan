import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("No database url")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE sales ADD COLUMN is_void BOOLEAN DEFAULT FALSE;"))
        print("Added is_void")
    except Exception as e:
        print(f"Error adding is_void: {e}")
        
    try:
        conn.execute(text("ALTER TABLE sales ADD COLUMN void_reason TEXT;"))
        print("Added void_reason")
    except Exception as e:
        print(f"Error adding void_reason: {e}")

    conn.commit()
    print("Done")
