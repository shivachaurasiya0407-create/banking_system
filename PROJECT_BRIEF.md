# SHIVA Banking System — Project Brief

## 1. Project kya hai?

Yeh ek educational banking-operations prototype hai. Staff is web portal se customer accounts, deposits, withdrawals, transfers, loans, fixed deposits aur audit records manage kar sakte hain. Web UI, API aur PostgreSQL database milkar kaam karte hain.

> **Important:** Yeh licensed bank nahi hai. Isme real paise, real customers, ya production banking ke liye approval/integration nahi hai. Sirf synthetic/test data use karein. SMS/email integration simulated notification log hai; koi real message deliver nahi hota.

## 2. Technology aur architecture

| Hissa | Technology | Kaam |
|---|---|---|
| Web portal | Next.js App Router, React, TypeScript, CSS | Staff sign-in, dashboard, forms, tables aur product workflows |
| API | FastAPI, Pydantic | Input validation, staff permissions, banking operations aur JSON responses |
| Database | PostgreSQL, SQLAlchemy | Staff/customers/accounts/branches, ledger, loans, FDs, audit aur notification records |
| Schema changes | Alembic | Versioned database migrations |
| Tests | pytest, FastAPI TestClient, SQLite test DB | API aur backend behavior ki automated jaanch |

### Request ka raasta

1. Browser par `app/page.tsx` ka interactive dashboard load hota hai.
2. Browser `/api/banking/...` ko request bhejta hai.
3. Next.js route handler sirf allowlisted API paths ko FastAPI tak forward karta hai. Staff access token HttpOnly `banking_session` cookie se liya jata hai; browser JavaScript token ko nahi padh sakta.
4. FastAPI token, role aur request schema verify karta hai.
5. `BankingService` validated operation ko PostgreSQL transaction mein ledger postings aur audit/notification records ke saath persist karta hai.
6. API result UI ko milta hai; successful banking actions idempotency key bhejte hain taaki retries se duplicate postings na hon.

## 3. Portal mein kya-kya hai?

### Login aur staff access

- Username/password login; failed logins par configurable lockout.
- Roles: `ADMIN`, `TELLER`, `AUDITOR`.
- Password badalne ki self-service screen; password 12–256 characters ka hona chahiye.
- Admin staff accounts bana, role/active status badal, aur password reset kar sakta hai. Password reset aur role/active change purane staff sessions revoke karte hain.
- Sign out par session cookie clear hoti hai.

### Dashboard aur accounts

- Account count, active/frozen/closed breakdown, total deposit balance, posted transaction count, outstanding loans aur active fixed-deposit summary.
- Account number ya customer name se search; `All`, `Active`, `Frozen`, `Closed` filters.
- Account details mein account type, branch/IFSC, status, balance aur customer KYC status.
- Admin account freeze/unfreeze kar sakta hai.
- Admin account ko sirf zero balance par permanently close kar sakta hai; non-zero balance par UI pehle funds clear karne ko kehta hai.
- Admin/Teller naya account khol sakte hain: customer details, supported Indian state, branch, account type (`SAVINGS`, `CURRENT`, `SALARY`) aur minimum opening deposit.
- Identity number raw form mein store nahi hota; service uska keyed fingerprint banati hai. Duplicate identity rokne ke liye fingerprint unique hota hai.
- Account activity aur date/type filterable statement; date range ka end date poore din ko include karta hai. Print/browser ke “Save as PDF” se paper/PDF export aur CSV download bhi available hai.

### Cash aur ledger operations

- Deposit, withdrawal aur account-to-account transfer; memo/remark optional.
- Transfer atomic double-entry postings ke roop mein hota hai. Amounts rupees mein dikhte hain, persistence minor units (paise) mein hoti hai.
- Har eligible write request idempotency key ke saath hoti hai.
- Admin posted activity row se reversal reason submit kar sakta hai. Reversal original record ko delete nahi karta; uske against nayi balancing ledger transaction banata hai.
- Admin monthly account interest post kar sakta hai; service per account/month duplicate accrual rokta hai.

### Customer profile aur KYC

- Customer Services tab mein account search karke linked customer record khola ja sakta hai.
- Admin/Teller phone, email aur address update kar sakte hain.
- Sirf Admin KYC ko `PENDING`, `VERIFIED`, ya `REJECTED` set kar sakta hai.
- Auditor customer service/profile changes nahi karta; account/KYC listing read-only rehti hai.

### Loans aur fixed deposits

- Loan applications account ke saath link hoti hain. Product types: personal, home, vehicle, education aur gold.
- Loan interest rate (maximum 36%), tenure (1–360 months), principal aur estimated EMI UI/API ke zariye submit hote hain.
- Admin loan approve/reject karta hai; approved loan disburse karta hai. Admin/Teller active loans ke repayments post kar sakte hain.
- Loan details screen repayment history, amount, principal aur interest breakdown dikhati hai.
- Fixed deposit (FD) active account se fund hota hai. Tenure 7–3650 days aur annual rate maximum 15% hoti hai.
- FD screen maturity date aur simple-interest-based projected maturity dikhati hai.
- Admin FD ko maturity ke baad close kar sakta hai ya premature close kar sakta hai (service ka penalty rule lagu hota hai). Portal maturity se pehle normal close disable karta hai.

### Branches, audit, notifications aur reconciliation

- Admin branch create kar sakta hai; branches account opening form mein selectable hain.
- Admin/Auditor audit trail dekh aur action text se filter kar sakte hain.
- Audit & Notifications screen simulated SMS/email log ko channel, recipient, message aur status ke saath dikhati hai.
- Reconciliation screen ledger balancing report chalati hai. Yeh account/ledger entries aur double-entry postings ke beech discrepancy report karta hai.

## 4. Role matrix

| Kaam | Admin | Teller | Auditor |
|---|:---:|:---:|:---:|
| Dashboard, account search, activity, statement | Haan | Haan | Haan |
| Account open, deposit, withdrawal, transfer | Haan | Haan | Nahi |
| Account freeze/unfreeze | Haan | Nahi | Nahi |
| Customer profile update | Haan | Haan | Nahi |
| KYC status update | Haan | Nahi | Nahi |
| Loan apply / view / repay | Haan | Haan | Read-only |
| Loan approve/reject/disburse | Haan | Nahi | Nahi |
| FD open / view | Haan | Haan | Read-only |
| FD close / premature close | Haan | Nahi | Nahi |
| Monthly interest / transaction reversal | Haan | Nahi | Nahi |
| Staff/branch management | Haan | Nahi | Nahi |
| Audit, notifications, reconciliation | Haan | Nahi | Haan |
| Apna password change | Haan | Haan | Haan |

Backend role checks asal security boundary hain. UI role ke hisaab se controls dikhata/chhupata hai, lekin authorization sirf UI par nirbhar nahi hai.

## 5. Database mein kya store hota hai?

- `staff_users`: staff identity, role, password hash, active/lockout state aur token version.
- `customers`: profile, KYC status aur identity fingerprint.
- `branches`, `accounts`: branch aur customer accounts (account status/type, balance in minor units, interest settings).
- `ledger_transactions`, `ledger_accounts`, `ledger_entries`: immutable operation records aur double-entry postings.
- `loans`, `loan_repayments`: application, approval/disbursement state, balance, EMI aur repayments.
- `fixed_deposits`: principal, rate, tenure, maturity aur closure information.
- `interest_accruals`: monthly accrual records aur duplicate-period guard.
- `audit_events`, `notification_logs`: staff actions aur simulated customer notification records.

Migration files `alembic/versions/` mein hain. Fresh database ko `alembic upgrade head` se latest schema par laya jata hai.

## 6. Important code locations

- `app/page.tsx` — portal pages, forms, state aur user actions.
- `app/globals.css` — responsive layout, dashboard, tables, modals aur print styling.
- `app/api/auth/` — login/logout aur secure session cookie.
- `app/api/banking/[...path]/route.ts` — authenticated, allowlisted FastAPI proxy.
- `banking_api/app.py` — API endpoints aur role checks.
- `banking_api/schemas.py` — request validation.
- `banking_api/service.py` — banking business rules, ledger, idempotency, loans/FD/interest/reversals.
- `banking_api/models.py` — SQLAlchemy database models.
- `banking_api/auth.py`, `banking_api/security.py` — staff auth, token aur password helpers.
- `alembic/versions/` — database migrations.
- `tests/` — backend tests.
- `OPERATIONS.md` — local operation guidance.

## 7. Local setup aur run

Prerequisites: supported Python runtime, Node.js/npm, Docker Desktop (ya local PostgreSQL 17) aur project dependencies.

1. `.env.example` ko local `.env` mein copy karein aur apne machine ke liye `POSTGRES_PASSWORD`, `DATABASE_URL`, `JWT_SECRET` (kam-se-kam 32 bytes), `PII_HMAC_KEY` (kam-se-kam 32 bytes), `CORS_ORIGINS` aur `BANKING_API_URL` set karein. Secrets ko source control mein commit na karein.
2. Dependencies install karein:

   ```powershell
   python -m pip install -r requirements.txt
   npm ci
   ```

3. PostgreSQL start karein (Docker Compose `docker-compose.yml` mein configured hai):

   ```powershell
   docker compose up -d postgres
   ```

4. Database schema migrate karein aur pehla administrator seed karein:

   ```powershell
   .\.venv\Scripts\alembic.exe upgrade head
   .\.venv\Scripts\python.exe -m banking_api.bootstrap_admin --seed-shiva
   ```

   Agar virtual environment abhi nahi hai, project Python commands ke liye apne chosen interpreter/venv ka istemal karein. Seed command existing administrator ko overwrite nahi karta. Initial access ke baad password badlein; `OPERATIONS.md` mein maujood bootstrap credential ko share/reuse na karein.

5. Alag terminals mein backend aur frontend start karein:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   npm run dev
   ```

6. Portal `http://localhost:3000` par kholein. API health `http://127.0.0.1:8000/healthz` aur database readiness `http://127.0.0.1:8000/readyz` se check ki ja sakti hai.

Configuration variables aur defaults ka canonical template `.env.example` hai.

## 8. Checks chalana

```powershell
npm run typecheck
npm run lint
npm run build
.\.venv\Scripts\python.exe -m pytest
```

Development environment aur PostgreSQL unavailable hon to application login/data workflows ko browser se verify nahi kiya ja sakta; API aur UI ko un services ke saath chala kar end-to-end test karein.

## 9. Abhi ki seemaen

- Koi real payment network, bank core, SMS gateway ya email provider connected nahi hai.
- UI staff operations portal hai, retail customer/mobile banking application nahi.
- API aur page kuch list screens mein pehle 50 records dikhate hain; bade production datasets ke liye pagination/filters ko aage badhana hoga.
- Production deployment se pehle security, privacy, regulatory requirements, database backup/restore, monitoring, accessibility aur operational review zaroori hain.
