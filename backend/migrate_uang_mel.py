import os
from sqlalchemy import create_engine, text

db_url = os.environ.get(
    "DATABASE_URL", 
    "postgresql+pg8000://postgres:password@localhost:5432/uang_pengiriman"
)

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_url = line.strip().split("=")[1]
                break

print(f"Connecting to {db_url}")
engine = create_engine(db_url)

with engine.begin() as conn:
    print("Checking if uang_mel_master exists...")
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name='uang_mel_master';
    """))
    exists = result.fetchone()

    if not exists:
        print("Creating uang_mel_master table...")
        conn.execute(text("""
            CREATE TABLE uang_mel_master (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
        """))
    else:
        print("Table uang_mel_master already exists.")

    print("Checking if uang_mel_id exists in vehicle_types...")
    result_col = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='vehicle_types' AND column_name='uang_mel_id';
    """))
    col_exists = result_col.fetchone()

    if not col_exists:
        print("Adding uang_mel_id to vehicle_types...")
        # Since we are dropping uang_mel and replacing it with uang_mel_id,
        # we can first add the column.
        conn.execute(text("ALTER TABLE vehicle_types ADD COLUMN uang_mel_id INTEGER NULL REFERENCES uang_mel_master(id) ON DELETE SET NULL;"))
        
        # We also need to remove the old uang_mel column if it exists.
        result_old = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='vehicle_types' AND column_name='uang_mel';
        """))
        if result_old.fetchone():
            print("Dropping old uang_mel column...")
            conn.execute(text("ALTER TABLE vehicle_types DROP COLUMN uang_mel;"))
        print("Columns updated successfully.")
    else:
        print("Column uang_mel_id already exists.")
