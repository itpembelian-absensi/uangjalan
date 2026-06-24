import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import json
sys.path.append('.')
from app.api import report_sales
import datetime

engine = create_engine("postgresql+pg8000://postgres:sa@localhost:5432/uang_pengiriman")
with Session(engine) as db:
    sales = report_sales(db=db, from_date=datetime.date(2026, 5, 25), to_date=datetime.date(2026, 6, 24))
    for s in sales:
        clist = s.get("customers_list", [])
        if "PT" in clist:
            print("FOUND EXACT 'PT' IN CUSTOMERS_LIST FOR SALE", s["sale_no"])
            print("list is:", clist)
