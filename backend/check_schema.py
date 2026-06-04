from app.db import engine
from sqlalchemy import text

conn = engine.connect()

r = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'cash_disbursements'"))
print([row[0] for row in r])
conn.close()
