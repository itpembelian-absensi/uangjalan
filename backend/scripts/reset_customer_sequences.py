from sqlalchemy import text

from app.db import engine

with engine.begin() as conn:
    conn.execute(
        text("SELECT setval(pg_get_serial_sequence('customers', 'id'), 1, false)")
    )
    conn.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('customer_vehicle_tariffs', 'id'), 1, false)"
        )
    )
print("Sequences reset.")
