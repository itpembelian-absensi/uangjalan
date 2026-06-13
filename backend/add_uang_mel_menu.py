import os
from sqlalchemy import create_engine, text

db_url = os.environ.get(
    "DATABASE_URL", 
    "postgresql+pg8000://postgres:password@localhost:5432/uang_pengiriman"
)

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_url = line.strip().split("=")[1]
                break

print(f"Connecting to {db_url}")
engine = create_engine(db_url)

with engine.begin() as conn:
    print("Checking if Uang Mel menu exists...")
    result = conn.execute(text("SELECT id FROM app_menus WHERE path = '/uang-mel'"))
    exists = result.fetchone()

    if not exists:
        print("Adding Uang Mel menu to app_menus...")
        conn.execute(text("""
            INSERT INTO app_menus (id, label, icon, path, section, sort_order, read_permission)
            VALUES ('master-uang-mel', 'Master Uang Mel', 'DollarSign', '/uang-mel', 'master', 85, 'view_master')
        """))
        
        # Get valid access level
        access_levels = conn.execute(text("SELECT DISTINCT access_level FROM role_menu_access")).fetchall()
        print("Valid access levels:", access_levels)
        valid_level = 'full'
        for lvl in access_levels:
            if 'write' in lvl[0].lower() or 'full' in lvl[0].lower() or 'yes' in lvl[0].lower() or 'edit' in lvl[0].lower():
                valid_level = lvl[0]
                break
        
        print(f"Using access level: {valid_level}")
        conn.execute(text(f"""
            INSERT INTO role_menu_access (role, menu_id, access_level)
            VALUES ('admin', 'master-uang-mel', '{valid_level}')
            ON CONFLICT DO NOTHING
        """))
        print("Access granted to admin.")
            
        print("Menu added successfully.")
    else:
        print("Menu Uang Mel already exists.")
