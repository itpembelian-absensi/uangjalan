from sqlalchemy import create_engine, text

engine = create_engine("postgresql+pg8000://postgres:sa@localhost:5432/uang_pengiriman")
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, name, gol23, gol45 FROM toll_sections WHERE name ILIKE '%balaraja%'"))
    for row in res:
        print(row)
