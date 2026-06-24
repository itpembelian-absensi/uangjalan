from sqlalchemy import create_engine, text

engine = create_engine("postgresql+pg8000://postgres:sa@localhost:5432/uang_pengiriman")
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, name FROM customers WHERE name ILIKE '%PROFITTO INOVASI KREATIF%'"))
    for row in res:
        print(row)
