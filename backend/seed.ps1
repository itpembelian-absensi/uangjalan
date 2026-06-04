$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
  python -m venv .venv
  .\.venv\Scripts\pip install -r requirements.txt
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Edit .env lalu jalankan lagi."
  exit 1
}

.\.venv\Scripts\python seed.py
