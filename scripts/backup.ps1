param([string]$DataDir = "data", [string]$BackupDir = "backups")
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $DataDir).Path
$workspace = (Resolve-Path -LiteralPath '.').Path
if (-not $source.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'DATA_DIR must be inside this workspace for this helper.' }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$target = Join-Path (Resolve-Path -LiteralPath $BackupDir).Path ("threeds-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Recurse
Write-Host "Backup created at $target"

