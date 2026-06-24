import json
from sqlalchemy import create_engine, text

engine = create_engine('postgresql+pg8000://postgres:sa@localhost:5432/uang_pengiriman')
with engine.connect() as conn:
    # Check customers with Jakarta-Merak in toll breakdown
    res = conn.execute(text(
        "SELECT id, name, custom_toll_breakdown FROM customers "
        "WHERE custom_toll_breakdown IS NOT NULL "
        "AND custom_toll_breakdown LIKE '%Merak%' LIMIT 5"
    )).mappings().fetchall()
    
    if not res:
        print("No customers found with 'Merak' in custom_toll_breakdown")
    
    for r in res:
        d = dict(r)
        print(f"\n=== Customer ID: {d['id']}, Name: {d['name']} ===")
        bd = json.loads(d['custom_toll_breakdown'])
        for seg in bd:
            if 'merak' in (seg.get('section_name') or '').lower():
                print(json.dumps(seg, indent=2))

    # Also check toll_sections for Jakarta-Merak
    print("\n\n=== Toll Sections containing 'Merak' ===")
    sections = conn.execute(text(
        "SELECT ts.id, ts.name, ts.network, ts.is_active, ts.gol23, ts.gol45 "
        "FROM toll_sections ts WHERE ts.name LIKE '%Merak%' ORDER BY ts.id"
    )).mappings().fetchall()
    for s in sections:
        print(dict(s))

    # Check toll_section_rates for those sections
    print("\n=== Toll Section Rates for Merak sections ===")
    rates = conn.execute(text(
        "SELECT tsr.section_id, ts.name as section_name, tg.code as gol_code, tg.name as gol_name, tsr.rate "
        "FROM toll_section_rates tsr "
        "JOIN toll_sections ts ON tsr.section_id = ts.id "
        "JOIN toll_golongan tg ON tsr.golongan_id = tg.id "
        "WHERE ts.name LIKE '%Merak%' "
        "ORDER BY tsr.section_id, tg.sort_order"
    )).mappings().fetchall()
    for r in rates:
        print(dict(r))

    # Check toll_gates for Merak sections
    print("\n=== Toll Gates for Merak sections ===")
    gates = conn.execute(text(
        "SELECT tg.id, tg.section_id, ts.name as section_name, tg.code, tg.name, tg.latitude, tg.longitude, tg.is_active "
        "FROM toll_gates tg "
        "JOIN toll_sections ts ON tg.section_id = ts.id "
        "WHERE ts.name LIKE '%Merak%' "
        "ORDER BY tg.section_id, tg.sort_order"
    )).mappings().fetchall()
    for g in gates:
        print(dict(g))

    # Check toll_gate_fares for Merak sections
    print("\n=== Toll Gate Fares for Merak sections (first 10) ===")
    fares = conn.execute(text(
        "SELECT tgf.id, tgf.entry_gate_id, eg.name as entry_name, tgf.exit_gate_id, xg.name as exit_name, "
        "tgl.code as gol_code, tgf.rate "
        "FROM toll_gate_fares tgf "
        "JOIN toll_gates eg ON tgf.entry_gate_id = eg.id "
        "JOIN toll_gates xg ON tgf.exit_gate_id = xg.id "
        "JOIN toll_sections ts ON eg.section_id = ts.id "
        "JOIN toll_golongan tgl ON tgf.golongan_id = tgl.id "
        "WHERE ts.name LIKE '%Merak%' "
        "ORDER BY tgf.id LIMIT 10"
    )).mappings().fetchall()
    for f in fares:
        print(dict(f))
