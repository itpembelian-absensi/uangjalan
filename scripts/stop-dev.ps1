# Hentikan proses dev backend/frontend project ini
$root = "Uang Pengiriman"

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Name -match '^(python|pythonw|uvicorn)\.exe$' -and
    $_.CommandLine -match "$root|uvicorn app\.main|uang.?pengiriman"
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "$root|concurrently|vite" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

foreach ($port in @(8001, 8002, 5173)) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
      if ($_ -and $_ -gt 0) {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
      }
    }
}

Write-Host "Proses dev dihentikan. Jalankan lagi: npm run dev"
