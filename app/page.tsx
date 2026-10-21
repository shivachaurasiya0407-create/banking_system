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
  status: string;
  memo?: string;
};
type StatementEntry = {
  transaction_id: string;
  date: string;
  type: string;
  credit: string;
  debit: string;
  running_balance: string;
  status: string;
  memo?: string;
};
type StatementData = {
  account_number: string;
  ifsc: string;
  status: string;
  current_balance: string;
  customer_name: string;
  total_credit: string;
  total_debit: string;
  entry_count: number;
  entries: StatementEntry[];
};
type AuditLog = {
  id: number;
  actor_username: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
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
  const [statusFilter, setStatusFilter] = useState<"ALL" | "ACTIVE" | "FROZEN" | "CLOSED">("ALL");
  const [selectedAccount, setSelectedAccount] = useState("");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [reconciliation, setReconciliation] = useState<string>("");
  const [staffMembers, setStaffMembers] = useState<Staff[]>([]);

  // Navigation tab
  const [activeTab, setActiveTab] = useState<"DASHBOARD" | "AUDIT" | "RECONCILIATION">("DASHBOARD");

  // Cash operations state
  const [action, setAction] = useState<"DEPOSIT" | "WITHDRAWAL">("DEPOSIT");
  const [amount, setAmount] = useState("");
  const [moneyAccount, setMoneyAccount] = useState("");
  const [moneyMemo, setMoneyMemo] = useState("");

  // Transfer state
  const [sender, setSender] = useState("");
  const [receiver, setReceiver] = useState("");
  const [transferAmount, setTransferAmount] = useState("");
  const [transferMemo, setTransferMemo] = useState("");

  // Admin staff creation
  const [newUsername, setNewUsername] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState<"TELLER" | "AUDITOR">("TELLER");
  const [newPassword, setNewPassword] = useState("");

  // Account opening
  const [branchIfsc, setBranchIfsc] = useState("");
  const [customerFirst, setCustomerFirst] = useState("");
  const [customerLast, setCustomerLast] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerAge, setCustomerAge] = useState("18");
  const [customerState, setCustomerState] = useState("");
  const [identityNumber, setIdentityNumber] = useState("");
  const [openingDeposit, setOpeningDeposit] = useState("2000.00");

  // Branch creation
  const [branchCode, setBranchCode] = useState("");
  const [branchName, setBranchName] = useState("");

  // Dynamic Statement modal state
  const [statementAccount, setStatementAccount] = useState<string | null>(null);
  const [statementData, setStatementData] = useState<StatementData | null>(null);
  const [statementStartDate, setStatementStartDate] = useState("");
  const [statementEndDate, setStatementEndDate] = useState("");
  const [statementKind, setStatementKind] = useState("");

  // Change password modal state
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPasswordInput, setNewPasswordInput] = useState("");
  const [confirmPasswordInput, setConfirmPasswordInput] = useState("");

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditSearch, setAuditSearch] = useState("");

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

  const loadAuditLogs = useCallback(async (actionFilter = "") => {
    const params = new URLSearchParams({ limit: "50", offset: "0" });
    if (actionFilter.trim()) params.set("action", actionFilter.trim());
    const logs = await api<AuditLog[]>(`admin/audit-logs?${params}`);
    setAuditLogs(logs);
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
          if (currentStaff.role === "ADMIN" || currentStaff.role === "AUDITOR") {
            await loadAuditLogs();
          }
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
  }, [loadDashboard, loadStaff, loadAuditLogs]);

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
      if (currentStaff.role === "ADMIN" || currentStaff.role === "AUDITOR") {
        await loadAuditLogs();
      }
      setNotice(`Welcome, ${currentStaff.full_name}. Data is persisted in PostgreSQL.`);
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

  async function openStatementModal(accountNumber: string) {
    setStatementAccount(accountNumber);
    await fetchStatementData(accountNumber, statementStartDate, statementEndDate, statementKind);
  }

  async function fetchStatementData(
    accountNumber: string,
    start = "",
    end = "",
    kind = "",
  ) {
    await run(async () => {
      const params = new URLSearchParams({ limit: "500", offset: "0" });
      if (start) params.set("start_at", new Date(start).toISOString());
      if (end) params.set("end_at", new Date(end).toISOString());
      if (kind) params.set("kind", kind);

      const data = await api<StatementData>(`accounts/${accountNumber}/statement?${params}`);
      setStatementData(data);
    });
  }

  async function handleStatementFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!statementAccount) return;
    await fetchStatementData(statementAccount, statementStartDate, statementEndDate, statementKind);
  }

  async function submitMoney(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api(`accounts/${moneyAccount}/${action === "DEPOSIT" ? "deposits" : "withdrawals"}`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ amount, memo: moneyMemo.trim() }),
      });
      setNotice(`${action === "DEPOSIT" ? "Deposit" : "Withdrawal"} of ₹${amount} posted successfully to PostgreSQL.`);
      setAmount("");
      setMoneyMemo("");
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
          memo: transferMemo.trim(),
        }),
      });
      setNotice(`Transfer of ₹${transferAmount} posted to PostgreSQL ledger.`);
      setTransferAmount("");
      setTransferMemo("");
      await loadDashboard();
      if (selectedAccount === sender || selectedAccount === receiver) {
        await selectAccount(selectedAccount);
      }
    });
  }

  async function changeStatus(accountNumber: string, status: string) {
    await run(async () => {
      await api(`accounts/${accountNumber}/status`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ status }),
      });
      setNotice(`Account ${accountNumber} status updated to ${status}.`);
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
      setNotice("Staff account created in PostgreSQL.");
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
      setNotice("New account opened and ledger entry recorded in PostgreSQL.");
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
      setNotice("Branch saved to PostgreSQL.");
      await loadDashboard();
    });
  }

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPasswordInput !== confirmPasswordInput) {
      setError("New passwords do not match.");
      return;
    }
    await run(async () => {
      await api("auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPasswordInput,
        }),
      });
      setPasswordModalOpen(false);
      setCurrentPassword("");
      setNewPasswordInput("");
      setConfirmPasswordInput("");
      setNotice("Password changed successfully. Token version incremented.");
    });
  }

  async function handleAuditFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await loadAuditLogs(auditSearch);
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

  const filteredAccounts = accounts.filter((acc) => {
    if (statusFilter === "ALL") return true;
    return acc.status === statusFilter;
  });

  if (!staff) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <div className="brand-mark">B</div>
          <p className="eyebrow">POSTGRESQL BANKING OPERATIONS</p>
          <h1>Secure Staff Sign In</h1>
          <p className="muted">All operations and data are stored securely in PostgreSQL.</p>
          {error && <p className="alert error">{error}</p>}
          <form className="stack" onSubmit={login}>
            <label>
              Username
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="e.g. shiva"
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
                placeholder="Enter password"
                required
              />
            </label>
            <button disabled={busy} type="submit">
              {busy ? "Authenticating…" : "Sign in securely"}
            </button>
          </form>
          <p className="fine-print">Administrator: Shiva Chaurasiya (username: shiva)</p>
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
            <span className="live-badge">
              <span className="live-dot" /> PostgreSQL Active
            </span>
          </div>
        </div>
        <div className="staff-menu">
          <div className="staff-avatar">{staff.full_name.slice(0, 1).toUpperCase()}</div>
          <div className="staff-meta">
            <strong>{staff.full_name}</strong>
            <span>{staff.role} · @{staff.username}</span>
          </div>
          <button
            className="button-quiet"
            onClick={() => setPasswordModalOpen(true)}
            disabled={busy}
            title="Change your password"
          >
            Change Password
          </button>
          <button className="button-quiet" onClick={logout} disabled={busy}>
            Sign out
          </button>
        </div>
      </header>

      <section className="page-heading">
        <div>
          <p className="eyebrow">POSTGRESQL ENTERPRISE LEDGER</p>
          <h1>Good day, {staff.full_name}</h1>
          <p className="muted">Direct PostgreSQL ledger storage with double-entry reconciliation.</p>
        </div>
        <button className="button-secondary" onClick={() => run(loadDashboard)} disabled={busy}>
          Refresh data
        </button>
      </section>

      {error && <p className="alert error">{error}</p>}
      {notice && <p className="alert success">{notice}</p>}

      <nav className="tabs">
        <button
          className={`tab-btn ${activeTab === "DASHBOARD" ? "active" : ""}`}
          onClick={() => setActiveTab("DASHBOARD")}
        >
          Banking Operations
        </button>
        {(staff.role === "ADMIN" || staff.role === "AUDITOR") && (
          <button
            className={`tab-btn ${activeTab === "AUDIT" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("AUDIT");
              loadAuditLogs();
            }}
          >
            Audit Trail
          </button>
        )}
        {(staff.role === "ADMIN" || staff.role === "AUDITOR") && (
          <button
            className={`tab-btn ${activeTab === "RECONCILIATION" ? "active" : ""}`}
            onClick={() => setActiveTab("RECONCILIATION")}
          >
            Reconciliation
          </button>
        )}
      </nav>

      {activeTab === "DASHBOARD" && (
        <>
          <section className="metric-grid">
            <article className="metric-card">
              <span>Total accounts</span>
              <strong>{summary?.accounts.total ?? "—"}</strong>
              <small>{summary?.accounts.active ?? 0} active in PostgreSQL</small>
            </article>
            <article className="metric-card">
              <span>Ledger balance</span>
              <strong>₹{summary?.total_balance ?? "—"}</strong>
              <small>Real-time customer deposits</small>
            </article>
            <article className="metric-card">
              <span>Posted transactions</span>
              <strong>{summary?.transactions ?? "—"}</strong>
              <small>Immutable double-entry rows</small>
            </article>
            <article className="metric-card">
              <span>Account health</span>
              <strong>{summary?.accounts.frozen ?? 0} frozen</strong>
              <small>{summary?.accounts.closed ?? 0} closed</small>
            </article>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Customer Accounts</h2>
                <div className="filter-pills" style={{ marginTop: "8px" }}>
                  {(["ALL", "ACTIVE", "FROZEN", "CLOSED"] as const).map((status) => (
                    <button
                      key={status}
                      className={`pill-btn ${statusFilter === status ? "active" : ""}`}
                      onClick={() => setStatusFilter(status)}
                    >
                      {status === "ALL" ? "All Accounts" : status}
                    </button>
                  ))}
                </div>
              </div>
              <form className="search-form" onSubmit={searchAccounts}>
                <input
                  aria-label="Search accounts"
                  placeholder="Search by account # or customer name…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <button className="button-secondary" disabled={busy}>Search</button>
              </form>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Customer</th>
                    <th>IFSC</th>
                    <th>Status</th>
                    <th>Balance</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAccounts.map((account) => (
                    <tr key={account.account_number}>
                      <td className="mono">{account.account_number}</td>
                      <td>{account.customer_name}</td>
                      <td className="mono">{account.ifsc}</td>
                      <td>
                        <span className={`status status-${account.status.toLowerCase()}`}>
                          {account.status}
                        </span>
                      </td>
                      <td><strong>₹{account.balance}</strong></td>
                      <td className="row-actions">
                        <button
                          className="text-button"
                          onClick={() => selectAccount(account.account_number)}
                        >
                          Activity
                        </button>
                        <button
                          className="text-button"
                          onClick={() => openStatementModal(account.account_number)}
                        >
                          Statement
                        </button>
                        {staff.role === "ADMIN" && account.status !== "CLOSED" && (
                          <button
                            className="text-button"
                            onClick={() =>
                              changeStatus(
                                account.account_number,
                                account.status === "FROZEN" ? "ACTIVE" : "FROZEN"
                              )
                            }
                          >
                            {account.status === "FROZEN" ? "Unfreeze" : "Freeze"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filteredAccounts.length === 0 && (
                    <tr>
                      <td colSpan={6} className="empty">No accounts match the current filter.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {selectedAccount && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Recent activity</h2>
                  <p className="muted">Live PostgreSQL entries for account {selectedAccount}</p>
                </div>
                <button
                  className="button-secondary"
                  onClick={() => openStatementModal(selectedAccount)}
                >
                  Generate full statement
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Type</th>
                      <th>Credit</th>
                      <th>Debit</th>
                      <th>Remark / Memo</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((transaction) => (
                      <tr key={transaction.transaction_id}>
                        <td>{new Date(transaction.date).toLocaleString()}</td>
                        <td><strong>{transaction.type}</strong></td>
                        <td style={{ color: transaction.credit ? "var(--green)" : "inherit" }}>
                          {transaction.credit ? `+₹${transaction.credit}` : "—"}
                        </td>
                        <td style={{ color: transaction.debit ? "var(--red)" : "inherit" }}>
                          {transaction.debit ? `-₹${transaction.debit}` : "—"}
                        </td>
                        <td>{transaction.memo || "—"}</td>
                        <td><span className="status">{transaction.status}</span></td>
                      </tr>
                    ))}
                    {transactions.length === 0 && (
                      <tr>
                        <td colSpan={6} className="empty">No activity found for this account.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {(staff.role === "ADMIN" || staff.role === "TELLER") && (
            <section className="work-grid">
              <article className="panel">
                <h2>Open an account</h2>
                <p className="muted">Identity numbers are cryptographically fingerprinted before saving.</p>
                <form className="stack" onSubmit={openAccount}>
                  <label>First name<input value={customerFirst} onChange={(event) => setCustomerFirst(event.target.value)} required /></label>
                  <label>Last name<input value={customerLast} onChange={(event) => setCustomerLast(event.target.value)} required /></label>
                  <label>Phone<input inputMode="tel" value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} required /></label>
                  <label>Age<input type="number" min={18} max={110} value={customerAge} onChange={(event) => setCustomerAge(event.target.value)} required /></label>
                  <label>State / union territory<select value={customerState} onChange={(event) => setCustomerState(event.target.value)} required><option value="">Select a state</option>{states.map((state) => <option key={state} value={state}>{state}</option>)}</select></label>
                  <label>Identity number (Aadhaar 12-digit)<input inputMode="numeric" pattern="[0-9]{12}" value={identityNumber} onChange={(event) => setIdentityNumber(event.target.value)} required /></label>
                  <label>Branch<select value={branchIfsc} onChange={(event) => setBranchIfsc(event.target.value)} required>{branches.map((branch) => <option key={branch.ifsc} value={branch.ifsc}>{branch.name} · {branch.ifsc}</option>)}</select></label>
                  <label>Opening deposit (₹, min 2000)<input inputMode="decimal" value={openingDeposit} onChange={(event) => setOpeningDeposit(event.target.value)} required /></label>
                  <button disabled={busy}>Open account in PostgreSQL</button>
                </form>
              </article>

              <article className="panel">
                <h2>Cash operation</h2>
                <p className="muted">Post a deposit or withdrawal with an optional memo & idempotency.</p>
                <form className="stack" onSubmit={submitMoney}>
                  <label>Operation
                    <select value={action} onChange={(event) => setAction(event.target.value as "DEPOSIT" | "WITHDRAWAL")}>
                      <option value="DEPOSIT">Deposit</option>
                      <option value="WITHDRAWAL">Withdrawal</option>
                    </select>
                  </label>
                  <label>Account number<input inputMode="numeric" pattern="[0-9]{10}" value={moneyAccount} onChange={(event) => setMoneyAccount(event.target.value)} placeholder="10-digit account number" required /></label>
                  <label>Amount (₹)<input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" required /></label>
                  <label>Remark / Note (Optional)<input value={moneyMemo} onChange={(event) => setMoneyMemo(event.target.value)} placeholder="e.g. Salary, Monthly rent, Cash deposit" /></label>
                  <button disabled={busy}>Post {action.toLowerCase()} to PostgreSQL</button>
                </form>
              </article>

              <article className="panel">
                <h2>Transfer funds</h2>
                <p className="muted">Atomic double-entry transfer between active accounts.</p>
                <form className="stack" onSubmit={submitTransfer}>
                  <label>From account<input inputMode="numeric" pattern="[0-9]{10}" value={sender} onChange={(event) => setSender(event.target.value)} placeholder="Sender 10-digit account" required /></label>
                  <label>To account<input inputMode="numeric" pattern="[0-9]{10}" value={receiver} onChange={(event) => setReceiver(event.target.value)} placeholder="Receiver 10-digit account" required /></label>
                  <label>Amount (₹)<input inputMode="decimal" value={transferAmount} onChange={(event) => setTransferAmount(event.target.value)} placeholder="0.00" required /></label>
                  <label>Transfer remark (Optional)<input value={transferMemo} onChange={(event) => setTransferMemo(event.target.value)} placeholder="e.g. Invoice #203, Vendor payment" /></label>
                  <button disabled={busy}>Submit secure transfer</button>
                </form>
              </article>

              {staff.role === "ADMIN" && (
                <article className="panel">
                  <h2>Add a branch</h2>
                  <p className="muted">Manage branch codes directly in PostgreSQL.</p>
                  <form className="stack" onSubmit={createBranch}>
                    <label>IFSC<input minLength={4} maxLength={20} pattern="[A-Za-z0-9]+" value={branchCode} onChange={(event) => setBranchCode(event.target.value.toUpperCase())} placeholder="e.g. SHIV0000003" required /></label>
                    <label>Branch name<input minLength={2} maxLength={150} value={branchName} onChange={(event) => setBranchName(event.target.value)} placeholder="Branch name and city" required /></label>
                    <button disabled={busy}>Add branch</button>
                  </form>
                  <div className="staff-list" style={{ marginTop: "14px" }}>
                    {branches.map((branch) => (
                      <div className="staff-row" key={branch.ifsc}>
                        <strong>{branch.name}</strong>
                        <span className="mono">{branch.ifsc}</span>
                      </div>
                    ))}
                  </div>
                </article>
              )}
            </section>
          )}

          {staff.role === "ADMIN" && (
            <section className="work-grid">
              <article className="panel">
                <h2>Create staff account</h2>
                <p className="muted">Assign role permissions for banking tellers or auditors.</p>
                <form className="stack" onSubmit={createStaff}>
                  <label>Full name<input value={newName} onChange={(event) => setNewName(event.target.value)} required /></label>
                  <label>Username<input minLength={3} value={newUsername} onChange={(event) => setNewUsername(event.target.value)} required /></label>
                  <label>Role<select value={newRole} onChange={(event) => setNewRole(event.target.value as "TELLER" | "AUDITOR")}><option value="TELLER">Teller</option><option value="AUDITOR">Auditor</option></select></label>
                  <label>Initial password<input type="password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="12+ chars with upper, lower, number" required /></label>
                  <button disabled={busy}>Create staff member</button>
                </form>
              </article>
              <article className="panel">
                <h2>Active staff accounts</h2>
                <p className="muted">Persisted in staff_users table with PBKDF2 hashes.</p>
                <div className="staff-list">
                  {staffMembers.map((member) => (
                    <div className="staff-row" key={member.id}>
                      <div>
                        <strong>{member.full_name}</strong>
                        <span>@{member.username}</span>
                      </div>
                      <span className="status">{member.role}</span>
                    </div>
                  ))}
                </div>
              </article>
            </section>
          )}
        </>
      )}

      {activeTab === "AUDIT" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>PostgreSQL Security Audit Trail</h2>
              <p className="muted">Every staff login, money transfer, and account modification is recorded here.</p>
            </div>
            <form className="search-form" onSubmit={handleAuditFilter}>
              <input
                placeholder="Filter action (e.g. login, transfer, open)…"
                value={auditSearch}
                onChange={(event) => setAuditSearch(event.target.value)}
              />
              <button className="button-secondary" disabled={busy}>Filter</button>
            </form>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Target Entity</th>
                  <th>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td><strong>{log.actor_name}</strong> <span className="muted">(@{log.actor_username})</span></td>
                    <td><span className="audit-meta-tag">{log.action}</span></td>
                    <td className="mono">{log.entity_type}:{log.entity_id}</td>
                    <td className="mono">{JSON.stringify(log.metadata)}</td>
                  </tr>
                ))}
                {auditLogs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="empty">No audit logs recorded yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activeTab === "RECONCILIATION" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Ledger reconciliation</h2>
              <p className="muted">Audit-proof double-entry balancing against PostgreSQL customer accounts.</p>
            </div>
            <button
              className="button-secondary"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const report = await api<unknown>("admin/reconciliation");
                  setReconciliation(JSON.stringify(report, null, 2));
                })
              }
            >
              Run reconciliation check
            </button>
          </div>
          {reconciliation ? (
            <pre className="report">{reconciliation}</pre>
          ) : (
            <p className="muted">Click &quot;Run reconciliation check&quot; to verify ledger sum zero.</p>
          )}
        </section>
      )}

      {/* Dynamic Statement Modal */}
      {statementAccount && (
        <div className="modal-overlay" onClick={() => setStatementAccount(null)}>
          <div className="modal-box wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>Account Statement: {statementAccount}</h2>
                <p className="muted">
                  Customer: {statementData?.customer_name} · IFSC: {statementData?.ifsc} · Status: {statementData?.status}
                </p>
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <button
                  className="button-secondary"
                  onClick={() => window.print()}
                  title="Print official statement receipt"
                >
                  Print / Save PDF
                </button>
                <button
                  className="modal-close"
                  onClick={() => setStatementAccount(null)}
                  title="Close"
                >
                  ✕
                </button>
              </div>
            </div>

            {statementData && (
              <section className="statement-summary-bar">
                <article>
                  <span>Current Balance</span>
                  <strong>₹{statementData.current_balance}</strong>
                </article>
                <article>
                  <span>Total Inflow (Credits)</span>
                  <strong style={{ color: "var(--green)" }}>+₹{statementData.total_credit}</strong>
                </article>
                <article>
                  <span>Total Outflow (Debits)</span>
                  <strong style={{ color: "var(--red)" }}>-₹{statementData.total_debit}</strong>
                </article>
                <article>
                  <span>Total Recorded Items</span>
                  <strong>{statementData.entry_count} entries</strong>
                </article>
              </section>
            )}

            <form className="statement-filter-form" onSubmit={handleStatementFilter}>
              <label>
                Start date
                <input
                  type="date"
                  value={statementStartDate}
                  onChange={(e) => setStatementStartDate(e.target.value)}
                />
              </label>
              <label>
                End date
                <input
                  type="date"
                  value={statementEndDate}
                  onChange={(e) => setStatementEndDate(e.target.value)}
                />
              </label>
              <label>
                Transaction type
                <select
                  value={statementKind}
                  onChange={(e) => setStatementKind(e.target.value)}
                >
                  <option value="">All Types</option>
                  <option value="OPENING_DEPOSIT">Opening Deposit</option>
                  <option value="DEPOSIT">Deposit</option>
                  <option value="WITHDRAWAL">Withdrawal</option>
                  <option value="TRANSFER">Transfer</option>
                </select>
              </label>
              <button className="button-secondary" disabled={busy}>Filter statement</button>
            </form>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date & Time</th>
                    <th>Type</th>
                    <th>Credit</th>
                    <th>Debit</th>
                    <th>Running Balance</th>
                    <th>Remark</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {statementData?.entries.map((entry) => (
                    <tr key={entry.transaction_id}>
                      <td>{new Date(entry.date).toLocaleString()}</td>
                      <td><strong>{entry.type}</strong></td>
                      <td style={{ color: entry.credit !== "0.00" ? "var(--green)" : "inherit" }}>
                        {entry.credit !== "0.00" ? `+₹${entry.credit}` : "—"}
                      </td>
                      <td style={{ color: entry.debit !== "0.00" ? "var(--red)" : "inherit" }}>
                        {entry.debit !== "0.00" ? `-₹${entry.debit}` : "—"}
                      </td>
                      <td className="mono">₹{entry.running_balance}</td>
                      <td>{entry.memo || "—"}</td>
                      <td><span className="status">{entry.status}</span></td>
                    </tr>
                  ))}
                  {(!statementData || statementData.entries.length === 0) && (
                    <tr>
                      <td colSpan={7} className="empty">No transactions found for this period.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      {passwordModalOpen && (
        <div className="modal-overlay" onClick={() => setPasswordModalOpen(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Change Password</h2>
              <button className="modal-close" onClick={() => setPasswordModalOpen(false)}>✕</button>
            </div>
            <form className="stack" onSubmit={handlePasswordChange}>
              <label>
                Current Password
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                  required
                />
              </label>
              <label>
                New Password
                <input
                  type="password"
                  minLength={12}
                  value={newPasswordInput}
                  onChange={(e) => setNewPasswordInput(e.target.value)}
                  placeholder="12+ chars with uppercase, lowercase, number"
                  required
                />
              </label>
              <label>
                Confirm New Password
                <input
                  type="password"
                  minLength={12}
                  value={confirmPasswordInput}
                  onChange={(e) => setConfirmPasswordInput(e.target.value)}
                  placeholder="Confirm new password"
                  required
                />
              </label>
              <button disabled={busy}>Update Password</button>
            </form>
          </div>
        </div>
      )}

      <footer>
        Secure PostgreSQL Banking Engine · All data stored in PostgreSQL · No CSV storage
      </footer>
    </main>
  );
}
