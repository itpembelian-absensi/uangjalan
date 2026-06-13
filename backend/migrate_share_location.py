import os
from sqlalchemy import create_engine, text

# Get database URL from .env file or default
db_url = os.environ.get(
    "DATABASE_URL", 
    "postgresql+pg8000://postgres:password@localhost:5432/uang_pengiriman"
)

# Parse from .env if present
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_url = line.strip().split("=")[1]
                break

print(f"Connecting to {db_url}")
engine = create_engine(db_url)

with engine.begin() as conn:
    print("Checking if share_location column exists in customers table...")
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='customers' AND column_name='share_location';
    """))
    exists = result.fetchone()

    if not exists:
        print("Adding share_location column...")
        conn.execute(text("ALTER TABLE customers ADD COLUMN share_location VARCHAR NULL;"))
        print("Column added successfully.")
    else:
        print("Column share_location already exists.")
