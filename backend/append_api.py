import sys

with open('app/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
content = content.replace('    AppSettingUpdate,\n)', '    AppSettingUpdate,\n    TollDataExport,\n)')

# Add routes
new_routes = '''

@router.get("/toll-data/export", response_model=TollDataExport, dependencies=[Depends(require_permission("toll:write"))])
def export_toll_data(db: Session = Depends(get_db)):
    golongan = db.execute(select(TollGolongan)).scalars().all()
    sections = db.execute(select(TollSection)).scalars().all()
    section_rates = db.execute(select(TollSectionRate)).scalars().all()
    gates = db.execute(select(TollGate)).scalars().all()
    gate_fares = db.execute(select(TollGateFare)).scalars().all()
    
    return TollDataExport(
        golongan=[{
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "description": g.description,
            "sort_order": g.sort_order,
            "is_active": g.is_active,
        } for g in golongan],
        sections=[{
            "id": s.id,
            "network": s.network,
            "name": s.name,
            "origin_name": s.origin_name,
            "destination_name": s.destination_name,
            "length_km": float(s.length_km),
            "gol23": float(s.gol23),
            "gol45": float(s.gol45),
            "sort_order": s.sort_order,
            "is_active": s.is_active,
        } for s in sections],
        section_rates=[{
            "section_id": r.section_id,
            "golongan_id": r.golongan_id,
            "rate": float(r.rate),
        } for r in section_rates],
        gates=[{
            "id": g.id,
            "section_id": g.section_id,
            "code": g.code,
            "name": g.name,
            "latitude": float(g.latitude) if g.latitude else None,
            "longitude": float(g.longitude) if g.longitude else None,
            "sort_order": g.sort_order,
            "is_active": g.is_active,
        } for g in gates],
        gate_fares=[{
            "entry_gate_id": f.entry_gate_id,
            "exit_gate_id": f.exit_gate_id,
            "golongan_id": f.golongan_id,
            "rate": float(f.rate),
        } for f in gate_fares],
    )

@router.post("/toll-data/import", dependencies=[Depends(require_permission("toll:write"))])
def import_toll_data(payload: TollDataExport, db: Session = Depends(get_db)):
    try:
        # Upsert TollGolongan
        existing_gol = {g.id: g for g in db.execute(select(TollGolongan)).scalars().all()}
        for g in payload.golongan:
            if g.id in existing_gol:
                obj = existing_gol[g.id]
                obj.name = g.name
                obj.code = g.code
                obj.description = g.description
                obj.sort_order = g.sort_order
                obj.is_active = g.is_active
            else:
                db.add(TollGolongan(**g.model_dump()))
        
        db.flush()

        # Wipe and Replace TollSections and Gates
        db.execute(delete(TollSection))
        db.execute(delete(TollGate))
        db.flush()

        for s in payload.sections:
            db.add(TollSection(**s.model_dump()))
        db.flush()
        
        for r in payload.section_rates:
            db.add(TollSectionRate(**r.model_dump()))
            
        for g in payload.gates:
            db.add(TollGate(**g.model_dump()))
        db.flush()
        
        for f in payload.gate_fares:
            db.add(TollGateFare(**f.model_dump()))
            
        db.commit()
        
        # Reset sequences
        from app.db_tools import _reset_all_sequences
        with db.connection() as conn:
            _reset_all_sequences(conn)
            db.commit()
            
        return {"detail": "Import berhasil"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Gagal import data: {str(e)}")

'''

content += new_routes

with open('app/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
