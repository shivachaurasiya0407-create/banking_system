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
- **Initial password**: `shiva@12345678`

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

6. **Account Filters & Controls**:
   - Filter customer accounts by status: `All`, `Active`, `Frozen`, `Closed`.
   - Search accounts by account number or customer name.
   - Instant freeze / unfreeze toggles.

7. **Security Headers & Protection**:
   - Enforces `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, strict CORS origin checks, and HttpOnly SameSite session cookies.
