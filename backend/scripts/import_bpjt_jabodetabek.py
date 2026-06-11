"""Impor tarif ruas tol + matriks gerbang Jabodetabek dari BPJT ke database."""

from __future__ import annotations

from app.bpjt_import_service import import_jabodetabek_all
from app.db import SessionLocal, init_db


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        result = import_jabodetabek_all(db)
        sec = result["sections"]
        gates = result["gates"]
        print(
            f"BPJT ruas: {sec['total']} ({sec['created']} baru, {sec['updated']} diperbarui)."
        )
        print(
            f"BPJT gerbang: {gates['sections_imported']} ruas, "
            f"{gates['gates_created']} gerbang baru, {gates['fares_created']} tarif pasangan."
        )
        if gates.get("sections_skipped"):
            print("Ruas dilewati (belum ada di DB):", ", ".join(gates["sections_skipped"]))
        print(f"Sumber: {sec.get('source_title')} — {sec.get('source_page')}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
