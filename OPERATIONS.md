# Banking System Operations

This project is an educational prototype, not an approved production banking system. Do not load real customer data or funds until qualified security, privacy, legal, and banking-domain reviews are complete.

## CSV to PostgreSQL migration

1. Back up `Accounts.csv` and `Transaction_history/` to a restricted location. Keep the originals unchanged until the database import and reconciliation are signed off.
2. Set `DATABASE_URL`, `JWT_SECRET`, and `PII_HMAC_KEY`; start PostgreSQL with `docker compose up -d postgres`.
3. Apply schema migrations with `alembic upgrade head` and create the first administrator with `python -m banking_api.bootstrap_admin`.
4. Run the importer in dry-run mode: `python -m banking_api.import_csv --accounts Accounts.csv --history Transaction_history`.
5. Resolve every reported data error, rerun dry-run, and review the account, customer, transaction, and ledger-entry counts.
6. Only after review, commit once with `python -m banking_api.import_csv --accounts Accounts.csv --history Transaction_history --apply`.
7. Check `GET /admin/reconciliation` and compare account totals to the source records. Keep legacy CSV writes stopped after cutover; the standalone CSV CLI is not yet routed to PostgreSQL.

The importer requires an empty target database, an active administrator, a migrated branch with matching IFSC, unique valid identity/account data, and transaction history whose calculated account balances exactly match `Accounts.csv`. Raw identity numbers are read only to calculate a keyed fingerprint and are not written to PostgreSQL. The current sample CSV IFSC values do not match the configured branch; correct and verify those records before attempting import. Missing or incomplete history is intentionally not guessed.

## Encrypted PostgreSQL backups

Install PostgreSQL client tools and GnuPG, configure a public-key recipient with `gpg --import <recipient-public-key-file>`, and set `GPG_RECIPIENT` plus `DATABASE_URL`. Then run:

```powershell
.\scripts\backup_postgres.ps1 -OutputDirectory backups
```

The script creates a custom-format `pg_dump`, encrypts it to the configured GPG recipient, and removes its temporary plaintext dump. Restrict access to the encrypted backup directory and the corresponding private key. Schedule this script using the host's scheduler and copy encrypted backups to a separate failure domain; the repository does not configure a scheduler or storage retention policy.

Restore into a dedicated recovery database first, not the live database:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://.../banking_recovery"
.\scripts\restore_postgres.ps1 -BackupFile .\backups\banking-YYYYMMDD-HHMMSS.dump.gpg -ConfirmTarget RESTORE
alembic upgrade head
```

After restore, verify `/readyz`, run ledger reconciliation, compare known account/transaction counts, and document the recovery time before directing application traffic to the recovered database. `pg_restore --clean` removes objects in the target database; verify the connection string carefully.

## API and migration checks

- Run the automated suite: `python -m pip install -r requirements-dev.txt` then `python -m pytest -q`.
- CI applies Alembic migrations to PostgreSQL and runs the Python tests.
- Configure `CORS_ORIGINS` as a comma-separated allowlist of exact trusted origins. Do not use `*` for a credentialed staff portal.
- Keep database/JWT/HMAC secrets out of source control and logs; rotate them through the deployment secret manager and plan HMAC rotation before changing identity fingerprints.
- Readiness (`/readyz`) verifies database connectivity; liveness (`/healthz`) only verifies that the process responds.

The staff web portal is not included in the current working tree. API operations, authorization, and input validation must remain authoritative if a client UI is added later.
