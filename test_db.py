import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import TollGate, TollGolongan, TollSection

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def main():
    db = SessionLocal()
    gates = db.query(TollGate).all()
    print("Gates:", [(g.id, g.name) for g in gates if "Jakarta" in g.name or "Dalam Kota" in g.name or g.name in ["Taman Mini", "Cibubur", "Gunung Putri", "Citeureup", "Cibinong", "Sentul Selatan", "Sentul Barat", "Bogor", "Ciawi"]])
    
    golongan = db.query(TollGolongan).all()
    print("Golongan:", [(g.id, g.code, g.name) for g in golongan])
    
    sections = db.query(TollSection).all()
    print("Sections:", [(s.id, s.name) for s in sections])

if __name__ == "__main__":
    main()
