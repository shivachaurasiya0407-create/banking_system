# Banking System Operations (PostgreSQL Enterprise Ledger)

This project is a high-security banking prototype featuring direct PostgreSQL persistence, double-entry ledger bookkeeping, PBKDF2 authentication, and a Next.js staff management portal.

## Admin Credentials
An administrator account is pre-configured in PostgreSQL:
- **Full Name**: `Shiva Chaurasiya`
- **Username**: `shiva`
- **Password**: `Shiva@12345678`
- **Role**: `ADMIN`

To re-seed or verify this administrator in PostgreSQL at any time:
```powershell
.\.venv\Scripts\python.exe -m banking_api.bootstrap_admin --seed-shiva
```

---

## Process to Run the Project

### 1. Database Setup (PostgreSQL)
Ensure PostgreSQL is running locally on port `5432` with credentials matching `.env`:
```ini
POSTGRES_PASSWORD=Shiva123@
DATABASE_URL=postgresql+psycopg://postgres:Shiva123%40@localhost:5432/banking_system
```
Apply migrations if starting with a fresh database:
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

### 2. Start the Backend API (FastAPI)
Run the Python backend server on `http://127.0.0.1:8000`:
```powershell
.\.venv\Scripts\python.exe main.py
```
Health & Readiness endpoints:
- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/readyz`

### 3. Start the Web Portal (Next.js)
Open a second terminal window and run:
```powershell
npm run dev
```
Open your browser and navigate to `http://localhost:3000`.

Sign in with:
- **Username**: `shiva`
- **Password**: `Shiva@12345678`

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
   - Enforces password complexity rules (12+ characters, uppercase, lowercase, numbers).

6. **Account Filters & Controls**:
   - Filter customer accounts by status: `All`, `Active`, `Frozen`, `Closed`.
   - Search accounts by account number or customer name.
   - Instant freeze / unfreeze toggles.

7. **Security Headers & Protection**:
   - Enforces `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, strict CORS origin checks, and HttpOnly SameSite session cookies.
