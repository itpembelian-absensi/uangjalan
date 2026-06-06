from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text("SELECT tgname FROM pg_trigger"))
    for r in res:
        print(r)
