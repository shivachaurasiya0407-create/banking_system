# Banking System Operations (Educational Prototype)

This is an educational banking operations prototype with PostgreSQL persistence, a double-entry ledger, staff authentication, and a Next.js management portal. It is not a licensed bank and is not approved to hold real customer data or move real funds. Use synthetic data only. It has no external bank/payment-provider integration.

## Admin Credentials
Create the initial administrator in PostgreSQL:
- **Full Name**: `Shiva Chaurasiya`
- **Username**: `shiva`
- **Initial password**: `shiva@12345678`
- **Role**: `ADMIN`

The seed command only creates the administrator if it does not already exist. It does not seed employee or customer accounts, and it will not overwrite an existing admin password. To create the admin:
```powershell
.\.venv\Scripts\python.exe -m banking_api.bootstrap_admin --seed-shiva
```
To intentionally reset the existing admin password back to the initial password, run:
```powershell
.\.venv\Scripts\python.exe -m banking_api.bootstrap_admin --reset-shiva
```
Change the initial password after signing in. Passwords must be at least 12 characters. Do not reuse this study-project credential anywhere else.

---

## Process to Run the Project

### 1. Database Setup (PostgreSQL)
Ensure PostgreSQL is running locally on port `5432` with credentials matching `.env`:
```ini
POSTGRES_PASSWORD=Shiva123@
DATABASE_URL=postgresql+psycopg://postgres:Shiva123%40@localhost:5432/banking_system
```
`npm run dev` applies pending database migrations before starting the API and portal. To apply them manually:
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

### 2. Start the API and Web Portal Together
From the project folder, run:
```powershell
npm run dev
```
This starts both the private FastAPI service and the Next.js portal. The terminal prints the current private IPv4 address and the matching portal URL each time it starts, so use that address rather than a previously saved IP. The portal listens on all network adapters; the API remains private to the host and browser requests reach it through the portal.

If another device cannot connect, make sure it is on the same trusted Wi-Fi/LAN and allow Node.js/Next.js through Windows Firewall on **Private networks** for TCP port `3000`. You can check the host's current address with `ipconfig`. Keep the network profile private, do not expose this prototype or its ports to the public internet, and use synthetic customer data only. The API and PostgreSQL database are not directly exposed to other devices.

To stop both services, press `Ctrl+C` in the terminal running `npm run dev`.

If port `8000` is already occupied, the launcher automatically tries the next
available port through `8099` and configures the portal proxy to use it. To
require one specific API port, set `BANKING_API_PORT` in the current PowerShell
session before starting; the launcher will report a clear error if that port is
busy.

Sign in with:
- **Username**: `shiva`
- **Initial password**: `shiva@12345678`

## Docker Deployment (Educational Use Only)

The repository includes a Docker Compose deployment for the portal, API, and
PostgreSQL. It is a self-hosted starting point, not an approved production
banking deployment. Use synthetic data only; do not expose it publicly or use
it to hold customer data or move real funds.

1. Install Docker Engine/Desktop with the Compose plugin on a trusted host.
2. Create a local deployment environment file and fill in unique secrets:
   ```powershell
   Copy-Item .env.example .env
   ```
   Replace `POSTGRES_PASSWORD` with a long URL-safe value containing only
   letters, digits, `_`, or `-`; it is also embedded in the API database URL.
   Set `JWT_SECRET` and `PII_HMAC_KEY` to different random values of at least
   32 bytes. Keep `.env` out of source control.
3. Build and start the deployment:
   ```powershell
   docker compose -f docker-compose.deploy.yml up --build -d
   ```
   The web portal is available at `http://localhost:3000` (or `WEB_PORT` if
   configured). The API and database have no published host ports; the portal
   talks to the API over the private Compose network. Database migrations run
   before the API starts, and health checks gate service startup.
4. Put a TLS-terminating reverse proxy in front of the web portal before any
   remote access. Do not publish the API or PostgreSQL ports. Restrict access
   to trusted users and networks.
5. Create the first admin with the bootstrap command inside the API container:
   ```powershell
   docker compose -f docker-compose.deploy.yml exec api python -m banking_api.bootstrap_admin --seed-shiva
   ```
   Change the initial password immediately. Back up the PostgreSQL volume
   securely and test restoring it before relying on the deployment.
6. Stop the stack with:
   ```powershell
   docker compose -f docker-compose.deploy.yml down
   ```
   This preserves the named database volume. `down -v` deletes the database
   volume and its data.

---

## Key Features & Security Enhancements

1. **Pure PostgreSQL Persistence (Zero CSV Dependency)**:
   - All customer profiles, bank accounts, branches, transactions, double-entry ledger entries, and audit logs are stored strictly in PostgreSQL.
   - All legacy `.csv` storage files have been eliminated.

2. **In-App Dynamic Statement Generator**:
   - Statements are dynamically retrieved from PostgreSQL via `/accounts/{account_number}/statement`.
   - Filter by date range (start date, end date) and transaction type.
   - Live summary metrics: Total Credits (+₹), Total Debits (-₹), Current Balance, Entry Count.
   - Print / Save as PDF support with clean print styling.

3. **Transaction Remarks / Memos**:
   - Post deposits, withdrawals, and transfers with custom remarks (e.g. Salary, Rent, Vendor invoice).
   - Stored in PostgreSQL `ledger_transactions.memo` and displayed in activity & statement tables.

4. **Security Audit Trail Explorer**:
   - Access real-time audit logs under the **Audit Trail** tab (restricted to `ADMIN` and `AUDITOR` roles).
   - Tracks staff logins, money operations, account freezes, and configuration changes.

5. **Self-Service Password Management**:
   - Authenticated staff can securely change their own password via `Change Password` in the topbar.
   - Requires passwords to be 12–256 characters; long passphrases are accepted without character-composition rules.
   - Each staff account can have one active device session. Sign out to release it; an administrator can review/revoke active staff sessions.
   - Staff sign-ins include timestamp and browser information in the administrative audit trail.

6. **KYC Operation Lock**:
   - Newly opened customer accounts remain locked while KYC is pending.
   - Account transactions, loan/FD operations, account status changes, and profile updates require verified KYC.
   - Rejected KYC is terminal and cannot be edited or re-approved.

7. **Account Filters & Controls**:
   - Filter customer accounts by status: `All`, `Active`, `Frozen`, `Closed`.
   - Search accounts by account number or customer name.
   - Instant freeze / unfreeze toggles.

8. **Security Headers & Protection**:
   - Enforces `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, strict CORS origin checks, and HttpOnly SameSite session cookies.
