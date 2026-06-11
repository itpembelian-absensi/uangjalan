import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import TollGate

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    db = SessionLocal()
    
    gate_coords = {
        "Jakarta Dalam Kota": (-6.244, 106.873),
        "Taman Mini": (-6.303, 106.891),
        "Cibubur": (-6.376, 106.902),
        "Gunung Putri": (-6.438, 106.892),
        "Citeureup": (-6.488, 106.883),
        "Cibinong": (-6.498, 106.873),
        "Sentul Selatan": (-6.568, 106.863),
        "Sentul Barat": (-6.562, 106.852),
        "Bogor": (-6.600, 106.820),
        "Ciawi": (-6.650, 106.848),
    }

    for name, coords in gate_coords.items():
        gates = db.query(TollGate).filter(TollGate.name == name).all()
        for gate in gates:
            gate.latitude = coords[0]
            gate.longitude = coords[1]
    
    db.commit()
    print("Coordinates updated successfully!")

if __name__ == "__main__":
    main()
