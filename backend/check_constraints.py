from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text("""
    SELECT conname, pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    WHERE conrelid = 'customers'::regclass;
    """))
    for row in res:
        print(row)
