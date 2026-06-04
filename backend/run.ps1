$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r requirements.txt

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example. Please edit password/user if needed."
}

.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

