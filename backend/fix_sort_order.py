import sys, os
sys.path.insert(0, os.getcwd())
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import TollSection

engine = create_engine('postgresql+pg8000://postgres:sa@localhost:5432/uang_pengiriman')
Session = sessionmaker(bind=engine)
db = Session()

# Get all sections ordered logically: by network, then name, then origin, then destination
rows = db.query(TollSection).order_by(
    TollSection.network,
    TollSection.name,
    TollSection.origin_name,
    TollSection.destination_name,
).all()

print(f"Total sections: {len(rows)}")
print(f"{'ID':>4} | {'Old':>4} | {'New':>4} | {'Network':15} | {'Name':50} | {'Origin':25} | {'Destination':25}")
print("-" * 140)

for i, r in enumerate(rows, start=1):
    old = r.sort_order
    r.sort_order = i
    net = (r.network or "")[:15]
    name = (r.name or "")[:50]
    orig = (r.origin_name or "")[:25]
    dest = (r.destination_name or "")[:25]
    print(f"{r.id:4d} | {old:4d} | {i:4d} | {net:15} | {name:50} | {orig:25} | {dest:25}")

db.commit()
print("\nDone! Sort orders updated.")
