from __future__ import annotations



from pathlib import Path



from pydantic_settings import BaseSettings, SettingsConfigDict



_BACKEND_DIR = Path(__file__).resolve().parents[2]

_ENV_FILE = _BACKEND_DIR / ".env"





class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )



    app_name: str = "Uang Pengiriman"

    database_url: str

    allow_origins: str = "http://localhost:8000"

    session_secret: str = "change-me"

    admin_username: str = "admin"

    admin_password: str = "admin"

    google_maps_api_key: str | None = None

    # OSRM routing (default: server publik project-osrm.org)
    osrm_base_url: str = "https://router.project-osrm.org/route/v1/driving"
    osrm_http_timeout: int = 30
    osrm_max_retries: int = 2

    # DB tools are available by default; set MODE=production to hide them
    mode: str = "development"
    db_tools_backup_dir: str = "/tmp/db_backups"



    # Acuan tarif tol Jabodetabek — Golongan II & III (rate_group 23)

    toll_japek_km: float = 73.0

    toll_japek_gol23: float = 40500.0

    toll_japek_gol45: float = 54000.0

    toll_jorr_km: float = 32.0

    toll_jorr_gol23: float = 25000.0

    toll_jorr_gol45: float = 33500.0

    toll_jakarta_inner_km: float = 15.0

    toll_jakarta_inner_gol23: float = 16500.0

    toll_jakarta_inner_gol45: float = 19000.0

    toll_jagorawi_km: float = 45.0

    toll_jagorawi_gol23: float = 12000.0

    toll_jagorawi_gol45: float = 17000.0



    @property

    def allow_origins_list(self) -> list[str]:

        return [x.strip() for x in self.allow_origins.split(",") if x.strip()]





settings = Settings()


