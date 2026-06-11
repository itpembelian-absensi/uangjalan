import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import TollGate, TollGateFare

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    db = SessionLocal()
    
    jag_gate = db.query(TollGate).filter(TollGate.name == "Jakarta IC", TollGate.section_id == 4).first()
    if not jag_gate:
        jag_gate = TollGate(name="Jakarta IC", code="JAKARTA_IC", section_id=4, is_active=True)
        db.add(jag_gate)
        db.commit()
        db.refresh(jag_gate)
    
    exit_names = ["Taman Mini", "Cibubur", "Gunung Putri", "Citeureup", "Cibinong", "Sentul Selatan", "Sentul Barat", "Bogor", "Ciawi"]
    exits = db.query(TollGate).filter(TollGate.name.in_(exit_names), TollGate.section_id == 4).all()
    exit_ids = [g.id for g in exits]
    
    fares = db.query(TollGateFare).filter(TollGateFare.entry_gate_id == 67, TollGateFare.exit_gate_id.in_(exit_ids)).all()
    
    for f in fares:
        f.entry_gate_id = jag_gate.id
        
    db.commit()
    print(f"Moved {len(fares)} fares to new gate ID {jag_gate.id} on Jagorawi")

if __name__ == "__main__":
    main()
