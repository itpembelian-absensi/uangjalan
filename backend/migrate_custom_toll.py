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
    cursor.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS custom_toll_breakdown TEXT;")
    print("Migration successful: added custom_toll_breakdown to customers")
except Exception as e:
    print(f"Error during migration: {e}")
finally:
    cursor.close()
    conn.close()
