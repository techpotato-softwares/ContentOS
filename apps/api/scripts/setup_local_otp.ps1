# ContentOS local OTP setup (Windows)
# Run from repo root OR apps/api.
# Usage:  powershell -ExecutionPolicy Bypass -File apps/api/scripts/setup_local_otp.ps1

$ErrorActionPreference = "Stop"
$ApiRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (Test-Path (Join-Path $PSScriptRoot "..\..\api")) {
  # scripts/ is under apps/api/scripts
  $ApiRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
}
Set-Location $ApiRoot

Write-Host "==> API root: $ApiRoot"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  throw "Missing .venv — create it in apps/api first."
}

# 1) Embedded Postgres (pg0) on 5433
Write-Host "==> Ensuring local Postgres on :5433 ..."
$py = ".\.venv\Scripts\python.exe"
& $py -c "from pg0 import list_instances; print([(i.name,i.port,i.running) for i in list_instances()])"

$pgJob = Start-Process -FilePath $py -ArgumentList "scripts\local_pg.py" -WorkingDirectory $ApiRoot -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3

# 2) Load .env keys into this shell for checks
Get-Content .\.env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
  $k, $v = $_.Split('=', 2)
  Set-Item -Path ("Env:" + $k.Trim()) -Value ($v.Trim().Trim('"'))
}
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:EMAIL_TRANSPORT = "local"

# 3) Tables + seed
Write-Host "==> init_db + seed ..."
& $py -c "import database as db; db._engine=None; db._SessionLocal=None; from database import init_db; init_db(); print('init_db ok')"
& $py scripts\seed.py

Write-Host ""
Write-Host "Setup ready."
Write-Host "  1) API:   .\.venv\Scripts\python.exe -m uvicorn src.dev_server:app --host 127.0.0.1 --port 4001"
Write-Host "  2) Web:   cd ..\web; npm run dev -- --host 127.0.0.1 --port 5173"
Write-Host "  3) Login: http://127.0.0.1:5173/login  -> Email OTP"
Write-Host "  4) Inbox: http://127.0.0.1:4001/dev/mailbox"
Write-Host "  Seed user email: demo@demo-co.local  (or superadmin@contentos.local)"
Write-Host "  Password login still works: demo / ChangeMe123!"
