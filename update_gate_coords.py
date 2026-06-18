"""Apply bundled toll gate coordinates to the database."""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.toll_gate_service import refresh_gate_coordinates


def main() -> None:
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    result = refresh_gate_coordinates(db)
    print(f"Updated {result['updated']} of {result['total']} gates")
    if result["skipped"]:
        print("Skipped:", ", ".join(result["skipped"]))


if __name__ == "__main__":
    main()
