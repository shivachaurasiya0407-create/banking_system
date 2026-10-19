"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Role = "ADMIN" | "TELLER" | "AUDITOR";
type Staff = { id: string; username: string; full_name: string; role: Role };
type Account = {
  account_number: string;
  ifsc: string;
  status: string;
  balance: string;
  customer_name: string;
};
type Branch = { ifsc: string; name: string };
type Summary = {
  accounts: { total: number; active: number; frozen: number; closed: number };
  total_balance: string;
  transactions: number;
};
type Transaction = {
  transaction_id: string;
  date: string;
  type: string;
  credit: string;
  debit: string;
  balance: string;
  status: string;
};

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/banking/${path}`, {
    ...options,
    cache: "no-store",
    headers: {
      ...(options.headers as Record<string, string> | undefined),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!response.ok) {
    if (response.status === 401 && path !== "auth/me" && typeof window !== "undefined") {
      window.dispatchEvent(new Event("banking:auth-expired"));
    }
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }
  return (await response.json()) as T;
}

function operationKey() {
  return crypto.randomUUID();
}

export default function Home() {
  const [staff, setStaff] = useState<Staff | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [states, setStates] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [selectedAccount, setSelectedAccount] = useState("");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [reconciliation, setReconciliation] = useState<string>("");
  const [staffMembers, setStaffMembers] = useState<Staff[]>([]);
  const [action, setAction] = useState<"DEPOSIT" | "WITHDRAWAL">("DEPOSIT");
  const [amount, setAmount] = useState("");
  const [moneyAccount, setMoneyAccount] = useState("");
  const [sender, setSender] = useState("");
  const [receiver, setReceiver] = useState("");
  const [transferAmount, setTransferAmount] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState<"TELLER" | "AUDITOR">("TELLER");
  const [newPassword, setNewPassword] = useState("");
  const [branchIfsc, setBranchIfsc] = useState("");
  const [customerFirst, setCustomerFirst] = useState("");
  const [customerLast, setCustomerLast] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerAge, setCustomerAge] = useState("18");
  const [customerState, setCustomerState] = useState("");
  const [identityNumber, setIdentityNumber] = useState("");
  const [openingDeposit, setOpeningDeposit] = useState("2000.00");
  const [branchCode, setBranchCode] = useState("");
  const [branchName, setBranchName] = useState("");

  const loadDashboard = useCallback(async () => {
    const [nextSummary, nextAccounts, nextBranches, nextStates] = await Promise.all([
      api<Summary>("dashboard/summary"),
      api<{ items: Account[] }>("accounts?limit=50&offset=0"),
      api<Branch[]>("branches"),
      api<string[]>("metadata/india-states"),
    ]);
    setSummary(nextSummary);
    setAccounts(nextAccounts.items);
    setBranches(nextBranches);
    setStates(nextStates);
  }, []);

  const loadStaff = useCallback(async () => {
    setStaffMembers(await api<Staff[]>("staff?limit=100&offset=0"));
  }, []);

  useEffect(() => {
    const expireSession = () => {
      setStaff(null);
      setSummary(null);
      setAccounts([]);
      setTransactions([]);
      setError("Your staff session has expired. Please sign in again.");
    };
    window.addEventListener("banking:auth-expired", expireSession);
    return () => window.removeEventListener("banking:auth-expired", expireSession);
  }, []);

  useEffect(() => {
    api<Staff>("auth/me")
      .then(async (currentStaff) => {
        setStaff(currentStaff);
        try {
          await loadDashboard();
          if (currentStaff.role === "ADMIN") await loadStaff();
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : "Could not load dashboard.");
        }
      })
      .catch((cause: unknown) => {
        if (!(cause instanceof Error) || cause.message !== "Authentication required.") {
          setError(cause instanceof Error ? cause.message : "Could not verify staff session.");
        }
        setStaff(null);
      });
  }, [loadDashboard, loadStaff]);

  async function run(actionToRun: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await actionToRun();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const body = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(body.detail ?? "Sign in failed.");
      const currentStaff = await api<Staff>("auth/me");
      setStaff(currentStaff);
      setPassword("");
      await loadDashboard();
      if (currentStaff.role === "ADMIN") await loadStaff();
      setNotice(`Welcome, ${currentStaff.full_name}.`);
    });
  }

  async function searchAccounts(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const params = new URLSearchParams({ limit: "50", offset: "0" });
      if (query.trim()) params.set("q", query.trim());
      const result = await api<{ items: Account[] }>(`accounts?${params}`);
      setAccounts(result.items);
    });
  }

  async function selectAccount(accountNumber: string) {
    setSelectedAccount(accountNumber);
    setMoneyAccount(accountNumber);
    await run(async () => {
      const rows = await api<Transaction[]>(
        `accounts/${accountNumber}/transactions?limit=25&offset=0`,
      );
      setTransactions(rows);
    });
  }

  async function submitMoney(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api(`accounts/${moneyAccount}/${action === "DEPOSIT" ? "deposits" : "withdrawals"}`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ amount }),
      });
      setNotice(`${action === "DEPOSIT" ? "Deposit" : "Withdrawal"} posted.`);
      setAmount("");
      await loadDashboard();
      if (selectedAccount) await selectAccount(selectedAccount);
    });
  }

  async function submitTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api("transfers", {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({
          sender_account: sender,
          receiver_account: receiver,
          amount: transferAmount,
        }),
      });
      setNotice("Transfer posted.");
      setTransferAmount("");
      await loadDashboard();
    });
  }

  async function changeStatus(accountNumber: string, status: string) {
    await run(async () => {
      await api(`accounts/${accountNumber}/status`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ status }),
      });
      setNotice(`Account ${accountNumber} updated.`);
      await loadDashboard();
    });
  }

  async function createStaff(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api("staff", {
        method: "POST",
        body: JSON.stringify({
          username: newUsername,
          full_name: newName,
          role: newRole,
          password: newPassword,
        }),
      });
      setNewUsername("");
      setNewName("");
      setNewPassword("");
      setNotice("Staff account created.");
      await loadStaff();
    });
  }

  async function openAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api("accounts", {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({
          customer: {
            first_name: customerFirst,
            last_name: customerLast,
            phone: customerPhone,
            age: Number(customerAge),
            country: "India",
            state: customerState,
            identity_number: identityNumber,
          },
          opening_deposit: openingDeposit,
          branch_ifsc: branchIfsc || branches[0]?.ifsc,
        }),
      });
      setCustomerFirst("");
      setCustomerLast("");
      setCustomerPhone("");
      setIdentityNumber("");
      setNotice("Account opened and opening deposit recorded.");
      await loadDashboard();
    });
  }

  async function createBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api("branches", {
        method: "POST",
        body: JSON.stringify({ ifsc: branchCode, name: branchName }),
      });
      setBranchCode("");
      setBranchName("");
      setNotice("Branch added.");
      await loadDashboard();
    });
  }

  async function logout() {
    await run(async () => {
      await fetch("/api/auth/logout", { method: "POST" });
      setStaff(null);
      setSummary(null);
      setAccounts([]);
      setTransactions([]);
    });
  }

  if (!staff) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <div className="brand-mark">B</div>
          <p className="eyebrow">BANKING OPERATIONS</p>
          <h1>Welcome back</h1>
          <p className="muted">Sign in with your staff account to continue.</p>
          {error && <p className="alert error">{error}</p>}
          <form className="stack" onSubmit={login}>
            <label>
              Username
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            <button disabled={busy} type="submit">
              {busy ? "Signing in…" : "Sign in securely"}
            </button>
          </form>
          <p className="fine-print">Staff access is monitored and audited.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark small">B</div>
          <div>
            <strong>Banking Operations</strong>
            <span>PostgreSQL-backed staff portal</span>
          </div>
        </div>
        <div className="staff-menu">
          <div className="staff-avatar">{staff.full_name.slice(0, 1).toUpperCase()}</div>
          <div className="staff-meta">
            <strong>{staff.full_name}</strong>
            <span>{staff.role}</span>
          </div>
          <button className="button-quiet" onClick={logout} disabled={busy}>
            Sign out
          </button>
        </div>
      </header>

      <section className="page-heading">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h1>Good day, {staff.full_name.split(" ")[0]}</h1>
          <p className="muted">Live account and ledger information from PostgreSQL.</p>
        </div>
        <button className="button-secondary" onClick={() => run(loadDashboard)} disabled={busy}>
          Refresh data
        </button>
      </section>

      {error && <p className="alert error">{error}</p>}
      {notice && <p className="alert success">{notice}</p>}

      <section className="metric-grid">
        <article className="metric-card">
          <span>Total accounts</span>
          <strong>{summary?.accounts.total ?? "—"}</strong>
          <small>{summary?.accounts.active ?? 0} active</small>
        </article>
        <article className="metric-card">
          <span>Ledger balance</span>
          <strong>₹{summary?.total_balance ?? "—"}</strong>
          <small>Across all accounts</small>
        </article>
        <article className="metric-card">
          <span>Transactions</span>
          <strong>{summary?.transactions ?? "—"}</strong>
          <small>Posted and recorded in the ledger</small>
        </article>
        <article className="metric-card">
          <span>Account status</span>
          <strong>{summary?.accounts.frozen ?? 0} frozen</strong>
          <small>{summary?.accounts.closed ?? 0} closed</small>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Accounts</h2>
            <p className="muted">Search by account number or customer name.</p>
          </div>
          <form className="search-form" onSubmit={searchAccounts}>
            <input
              aria-label="Search accounts"
              placeholder="Search accounts…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <button className="button-secondary" disabled={busy}>Search</button>
          </form>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Account</th><th>Customer</th><th>IFSC</th><th>Status</th><th>Balance</th><th /></tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.account_number}>
                  <td className="mono">{account.account_number}</td>
                  <td>{account.customer_name}</td>
                  <td className="mono">{account.ifsc}</td>
                  <td><span className={`status status-${account.status.toLowerCase()}`}>{account.status}</span></td>
                  <td>₹{account.balance}</td>
                  <td className="row-actions">
                    <button className="text-button" onClick={() => selectAccount(account.account_number)}>Activity</button>
                    {staff.role === "ADMIN" && account.status !== "CLOSED" && (
                      <button
                        className="text-button"
                        onClick={() => changeStatus(account.account_number, account.status === "FROZEN" ? "ACTIVE" : "FROZEN")}
                      >
                        {account.status === "FROZEN" ? "Unfreeze" : "Freeze"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {accounts.length === 0 && <tr><td colSpan={6} className="empty">No accounts found.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {selectedAccount && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recent activity</h2>
              <p className="muted">Account {selectedAccount}</p>
            </div>
            <a className="text-button" href={`/api/banking/accounts/${selectedAccount}/statement.csv`}>
              Download statement
            </a>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Type</th><th>Credit</th><th>Debit</th><th>Balance</th><th>Status</th></tr></thead>
              <tbody>
                {transactions.map((transaction) => (
                  <tr key={transaction.transaction_id}>
                    <td>{new Date(transaction.date).toLocaleString()}</td>
                    <td>{transaction.type}</td>
                    <td>{transaction.credit ? `₹${transaction.credit}` : "—"}</td>
                    <td>{transaction.debit ? `₹${transaction.debit}` : "—"}</td>
                    <td>₹{transaction.balance}</td>
                    <td>{transaction.status}</td>
                  </tr>
                ))}
                {transactions.length === 0 && <tr><td colSpan={6} className="empty">No activity for this account.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(staff.role === "ADMIN" || staff.role === "TELLER") && (
        <section className="work-grid">
          <article className="panel">
            <h2>Open an account</h2>
            <p className="muted">Identity numbers are fingerprinted before they are stored.</p>
            <form className="stack" onSubmit={openAccount}>
              <label>First name<input value={customerFirst} onChange={(event) => setCustomerFirst(event.target.value)} required /></label>
              <label>Last name<input value={customerLast} onChange={(event) => setCustomerLast(event.target.value)} required /></label>
              <label>Phone<input inputMode="tel" value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} required /></label>
              <label>Age<input type="number" min={18} max={110} value={customerAge} onChange={(event) => setCustomerAge(event.target.value)} required /></label>
              <label>State / union territory<select value={customerState} onChange={(event) => setCustomerState(event.target.value)} required><option value="">Select a state</option>{states.map((state) => <option key={state} value={state}>{state}</option>)}</select></label>
              <label>Identity number<input inputMode="numeric" pattern="[0-9]{12}" value={identityNumber} onChange={(event) => setIdentityNumber(event.target.value)} required /></label>
              <label>Branch<select value={branchIfsc} onChange={(event) => setBranchIfsc(event.target.value)} required>{branches.map((branch) => <option key={branch.ifsc} value={branch.ifsc}>{branch.name} · {branch.ifsc}</option>)}</select></label>
              <label>Opening deposit (₹)<input inputMode="decimal" value={openingDeposit} onChange={(event) => setOpeningDeposit(event.target.value)} required /></label>
              <button disabled={busy}>Open account</button>
            </form>
          </article>
          <article className="panel">
            <h2>Cash operation</h2>
            <p className="muted">Post a deposit or withdrawal with an idempotency key.</p>
            <form className="stack" onSubmit={submitMoney}>
              <label>Operation
                <select value={action} onChange={(event) => setAction(event.target.value as "DEPOSIT" | "WITHDRAWAL")}>
                  <option value="DEPOSIT">Deposit</option>
                  <option value="WITHDRAWAL">Withdrawal</option>
                </select>
              </label>
              <label>Account number<input inputMode="numeric" pattern="[0-9]{10}" value={moneyAccount} onChange={(event) => setMoneyAccount(event.target.value)} required /></label>
              <label>Amount (₹)<input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} required /></label>
              <button disabled={busy}>Post operation</button>
            </form>
          </article>
          <article className="panel">
            <h2>Transfer funds</h2>
            <p className="muted">Transfer between active accounts.</p>
            <form className="stack" onSubmit={submitTransfer}>
              <label>From account<input inputMode="numeric" pattern="[0-9]{10}" value={sender} onChange={(event) => setSender(event.target.value)} required /></label>
              <label>To account<input inputMode="numeric" pattern="[0-9]{10}" value={receiver} onChange={(event) => setReceiver(event.target.value)} required /></label>
              <label>Amount (₹)<input inputMode="decimal" value={transferAmount} onChange={(event) => setTransferAmount(event.target.value)} required /></label>
              <button disabled={busy}>Submit transfer</button>
            </form>
          </article>
        </section>
      )}

      {(staff.role === "ADMIN" || staff.role === "AUDITOR") && (
        <section className="panel">
          <div className="panel-heading">
            <div><h2>Ledger reconciliation</h2><p className="muted">Verify account balances against posted ledger entries.</p></div>
            <button className="button-secondary" disabled={busy} onClick={() => run(async () => {
              const report = await api<unknown>("admin/reconciliation");
              setReconciliation(JSON.stringify(report, null, 2));
            })}>Run reconciliation</button>
          </div>
          {reconciliation && <pre className="report">{reconciliation}</pre>}
        </section>
      )}

      {staff.role === "ADMIN" && (
        <section className="work-grid">
          <article className="panel">
            <h2>Add a branch</h2>
            <p className="muted">Keep account-opening branch codes managed in PostgreSQL.</p>
            <form className="stack" onSubmit={createBranch}>
              <label>IFSC<input minLength={4} maxLength={20} pattern="[A-Za-z0-9]+" value={branchCode} onChange={(event) => setBranchCode(event.target.value.toUpperCase())} required /></label>
              <label>Branch name<input minLength={2} maxLength={150} value={branchName} onChange={(event) => setBranchName(event.target.value)} required /></label>
              <button disabled={busy}>Add branch</button>
            </form>
            <div className="staff-list">
              {branches.map((branch) => <div className="staff-row" key={branch.ifsc}><strong>{branch.name}</strong><span className="mono">{branch.ifsc}</span></div>)}
            </div>
          </article>
          <article className="panel">
            <h2>Create staff account</h2>
            <p className="muted">Assign the least-privilege role needed for each staff member.</p>
            <form className="stack" onSubmit={createStaff}>
              <label>Full name<input value={newName} onChange={(event) => setNewName(event.target.value)} required /></label>
              <label>Username<input minLength={3} value={newUsername} onChange={(event) => setNewUsername(event.target.value)} required /></label>
              <label>Role<select value={newRole} onChange={(event) => setNewRole(event.target.value as "TELLER" | "AUDITOR")}><option value="TELLER">Teller</option><option value="AUDITOR">Auditor</option></select></label>
              <label>Initial password<input type="password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></label>
              <button disabled={busy}>Create staff member</button>
            </form>
          </article>
          <article className="panel">
            <h2>Staff access</h2>
            <p className="muted">Active roles are controlled by the banking API.</p>
            <div className="staff-list">
              {staffMembers.map((member) => (
                <div className="staff-row" key={member.id}>
                  <div><strong>{member.full_name}</strong><span>{member.username}</span></div>
                  <span className="status">{member.role}</span>
                </div>
              ))}
            </div>
          </article>
        </section>
      )}

      <footer>All account operations are authorized and audited by the PostgreSQL API.</footer>
    </main>
  );
}
