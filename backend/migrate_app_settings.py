from app.db import engine
from sqlalchemy import text

def migrate():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE app_settings ADD COLUMN logo_base64 TEXT;"))
            print("Added logo_base64")
        except Exception as e:
            print("Error adding logo_base64:", e)
            
        try:
            conn.execute(text("ALTER TABLE app_settings ADD COLUMN favicon_base64 TEXT;"))
            print("Added favicon_base64")
        except Exception as e:
            print("Error adding favicon_base64:", e)

if __name__ == "__main__":
    migrate()
