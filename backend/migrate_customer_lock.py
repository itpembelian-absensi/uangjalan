import os
from dotenv import load_dotenv
import pg8000
from urllib.parse import urlparse

load_dotenv()
db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:sa@localhost:5432/uang_pengiriman")
url = urlparse(db_url)

conn = pg8000.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
conn.autocommit = True
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE;")
    cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;")
    cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL;")
    print("Migration successful: added is_locked, updated_at, updated_by_id to customers")
except Exception as e:
    print(f"Error during migration: {e}")
finally:
    cursor.close()
    conn.close()
