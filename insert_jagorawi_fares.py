import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import TollGate, TollGolongan, TollSection, TollGateFare

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_or_create_section(db, name):
    section = db.query(TollSection).filter(TollSection.name == name).first()
    if not section:
        section = TollSection(name=name, network="Jasa Marga", length_km=50.0)
        db.add(section)
        db.commit()
        db.refresh(section)
    return section

def get_or_create_gate(db, name, section_id):
    gate = db.query(TollGate).filter(TollGate.name == name).first()
    if not gate:
        code = name.upper().replace(" ", "_")
        gate = TollGate(name=name, code=code, section_id=section_id)
        db.add(gate)
        db.commit()
        db.refresh(gate)
    return gate

def main():
    db = SessionLocal()
    
    # Using existing Jagorawi section or creating it
    section = get_or_create_section(db, "Jagorawi")
    
    # Find golongans
    gol_map = {
        "Gol I": db.query(TollGolongan).filter(TollGolongan.code == "I").first(),
        "Gol II": db.query(TollGolongan).filter(TollGolongan.code == "II").first(),
        "Gol III": db.query(TollGolongan).filter(TollGolongan.code == "III").first(),
        "Gol IV": db.query(TollGolongan).filter(TollGolongan.code == "IV").first(),
        "Gol V": db.query(TollGolongan).filter(TollGolongan.code == "V").first(),
    }
    
    if not all(gol_map.values()):
        print("Missing golongans in DB!")
        return
        
    entry_gate = get_or_create_gate(db, "Jakarta Dalam Kota", section.id)
    
    fares_data = [
        {"exit": "Taman Mini", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Cibubur", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Gunung Putri", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Citeureup", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Cibinong", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Sentul Selatan", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Sentul Barat", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Bogor", "rates": [8000, 12000, 12000, 17000, 17000]},
        {"exit": "Ciawi", "rates": [8000, 12000, 12000, 17000, 17000]},
    ]
    
    gol_keys = ["Gol I", "Gol II", "Gol III", "Gol IV", "Gol V"]
    
    added = 0
    for row in fares_data:
        exit_gate = get_or_create_gate(db, row["exit"], section.id)
        
        for i, gol_key in enumerate(gol_keys):
            rate = row["rates"][i]
            gol = gol_map[gol_key]
            
            # Check if exists
            existing = db.query(TollGateFare).filter(
                TollGateFare.entry_gate_id == entry_gate.id,
                TollGateFare.exit_gate_id == exit_gate.id,
                TollGateFare.golongan_id == gol.id
            ).first()
            
            if existing:
                existing.rate = rate
            else:
                new_fare = TollGateFare(
                    entry_gate_id=entry_gate.id,
                    exit_gate_id=exit_gate.id,
                    golongan_id=gol.id,
                    rate=rate
                )
                db.add(new_fare)
            added += 1
            
    db.commit()
    print(f"Successfully added/updated {added} fares.")

if __name__ == "__main__":
    main()
