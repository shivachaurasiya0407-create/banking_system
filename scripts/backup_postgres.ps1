param(
    [string]$OutputDirectory = "backups"
)

$ErrorActionPreference = "Stop"
if (-not $env:DATABASE_URL) { throw "Set DATABASE_URL before running this script." }
if (-not $env:GPG_RECIPIENT) { throw "Set GPG_RECIPIENT to the backup recipient's public-key identity." }
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) { throw "pg_dump is required (install PostgreSQL client tools)." }
if (-not (Get-Command gpg -ErrorAction SilentlyContinue)) { throw "gpg is required." }

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$encryptedPath = Join-Path $OutputDirectory "banking-$stamp.dump.gpg"
$plainPath = "$encryptedPath.plain"
try {
    & pg_dump --format=custom --no-owner --no-acl --file $plainPath $env:DATABASE_URL
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE." }
    & gpg --batch --yes --trust-model always --recipient $env:GPG_RECIPIENT --output $encryptedPath --encrypt $plainPath
    if ($LASTEXITCODE -ne 0) { throw "GPG encryption failed with exit code $LASTEXITCODE." }
    Write-Output "Encrypted PostgreSQL backup created: $encryptedPath"
}
finally {
    if (Test-Path $plainPath) { Remove-Item -Force $plainPath }
}
