import pg8000
from urllib.parse import urlparse

url = urlparse("postgresql://postgres:sa@localhost:5432/uang_pengiriman")

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
    cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS force_toll BOOLEAN DEFAULT FALSE;")
    print("Migration successful: added force_toll to customers")
except Exception as e:
    print(f"Error during migration: {e}")
finally:
    cursor.close()
    conn.close()
