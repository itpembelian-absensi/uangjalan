from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text("""
    SELECT i.relname AS index_name, a.attname AS column_name
    FROM pg_class t, pg_class i, pg_index ix, pg_attribute a
    WHERE t.oid = ix.indrelid
      AND i.oid = ix.indexrelid
      AND a.attrelid = t.oid
      AND a.attnum = ANY(ix.indkey)
      AND t.relkind = 'r'
      AND t.relname = 'customers'
      AND ix.indisunique = true;
    """))
    for row in res:
        print(row)
