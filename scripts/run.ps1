$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.venv')) { py -3 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env'; Write-Warning 'Edit .env and replace APP_SECRET before public use.' }
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1

