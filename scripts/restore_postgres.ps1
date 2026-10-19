param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [Parameter(Mandatory = $true)]
    [string]$ConfirmTarget
)

$ErrorActionPreference = "Stop"
if ($ConfirmTarget -cne "RESTORE") { throw "Pass -ConfirmTarget RESTORE to confirm that the target database will be overwritten." }
if (-not $env:DATABASE_URL) { throw "Set DATABASE_URL before running this script." }
if (-not (Test-Path $BackupFile -PathType Leaf)) { throw "Backup file not found: $BackupFile" }
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) { throw "pg_restore is required (install PostgreSQL client tools)." }
if (-not (Get-Command gpg -ErrorAction SilentlyContinue)) { throw "gpg is required." }

$plainPath = Join-Path ([IO.Path]::GetTempPath()) ("banking-restore-" + [guid]::NewGuid().ToString("N") + ".dump")
try {
    & gpg --batch --output $plainPath --decrypt $BackupFile
    if ($LASTEXITCODE -ne 0) { throw "GPG decryption failed with exit code $LASTEXITCODE." }
    & pg_restore --clean --if-exists --no-owner --no-acl --dbname $env:DATABASE_URL $plainPath
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE." }
    Write-Output "Restore completed. Run the application's health and reconciliation checks before reopening access."
}
finally {
    if (Test-Path $plainPath) { Remove-Item -Force $plainPath }
}
