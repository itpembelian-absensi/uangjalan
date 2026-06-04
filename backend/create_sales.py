from app.db import engine
from sqlalchemy import text

conn = engine.connect()

# Drop delivery_notes if exists (to avoid confusion)
conn.execute(text("DROP TABLE IF EXISTS delivery_notes CASCADE;"))

# Create sales table
conn.execute(text("""
CREATE TABLE IF NOT EXISTS sales (
  id BIGSERIAL PRIMARY KEY,
  sale_no TEXT NOT NULL UNIQUE,
  date DATE NOT NULL,
  vehicle_id BIGINT NOT NULL REFERENCES vehicles(id) ON UPDATE CASCADE,
  driver_id BIGINT NOT NULL REFERENCES drivers(id) ON UPDATE CASCADE,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""))

# Create sale_details table
conn.execute(text("""
CREATE TABLE IF NOT EXISTS sale_details (
  id BIGSERIAL PRIMARY KEY,
  sale_id BIGINT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  customer_id BIGINT NOT NULL REFERENCES customers(id) ON UPDATE CASCADE,
  amount NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""))

conn.commit()
conn.close()
print("Tables sales and sale_details created successfully.")
