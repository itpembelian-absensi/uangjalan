from sqlalchemy import create_engine, text
import json

engine = create_engine("postgresql+pg8000://postgres:sa@localhost:5432/uang_pengiriman")
with engine.connect() as conn:
    res = conn.execute(text("SELECT name, network FROM toll_sections ORDER BY name ASC"))
    sections = [{"name": row[0], "network": row[1]} for row in res]

print(json.dumps(sections, indent=2))
