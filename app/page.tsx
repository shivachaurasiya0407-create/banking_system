"use client";

import { Fragment, FormEvent, useCallback, useEffect, useState } from "react";
import { ChartNoAxesColumn, LayoutDashboard, Landmark, Scale, ShieldCheck, UserRoundPlus, UsersRound } from "lucide-react";

type Role = "ADMIN" | "TELLER" | "AUDITOR";
type Staff = { id: string; username: string; full_name: string; role: Role };
type StaffSession = { id: string; staff: Staff };
type StaffMember = Staff & {
  active: boolean;
  created_at?: string;
  last_login_at?: string | null;
  signed_in?: boolean;
};
type Account = {
  account_number: string;
  ifsc: string;
  status: string;
  balance: string;
  customer_name: string;
  account_type?: string;
  kyc_status?: string;
};
type AccountAllowance = {
  daily_withdrawal_limit: string;
  daily_withdrawn_today: string;
  daily_withdrawal_remaining: string;
  kyc_status: string;
};
type OperationResult = {
  transaction_id: string;
  account_numbers: string[];
  balances: string[];
};
type TransactionReceipt = {
  transaction_id: string;
  type: string;
  amount: string;
  accounts: string[];
  balances: string[];
  memo: string;
  created_at: string;
};
type Branch = { ifsc: string; name: string };
type Summary = {
  accounts: { total: number; active: number; frozen: number; closed: number };
  total_balance: string;
  transactions: number;
  loans?: { active: number; applied: number; approved: number; outstanding: string };
  fixed_deposits?: { active: number; total_value: string };
};
type Loan = {
  loan_id: string;
  customer_name: string;
  kyc_status: string;
  loan_type: string;
  status: string;
  principal: string;
  outstanding: string;
  emi: string;
  interest_rate_annual: string;
  tenure_months: number;
  next_emi_date: string | null;
  created_at: string;
};
type FixedDeposit = {
  fd_id: string;
  customer_name: string;
  kyc_status: string;
  status: string;
  principal: string;
  interest_rate_annual: string;
  tenure_days: number;
  maturity_date: string;
  maturity_amount: string;
  opened_at: string;
};
type CustomerDetails = {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email?: string | null;
  address_line1?: string | null;
  address_city?: string | null;
  address_pin?: string | null;
  kyc_status: string;
};
type LoanDetails = Omit<Loan, "created_at"> & {
  disbursed_at?: string | null;
  memo: string;
  repayments: { id: string; amount: string; principal: string; interest: string; date: string }[];
};
type NotificationLog = {
  id: number;
  channel: string;
  recipient: string;
  subject: string;
  body: string;
  status: string;
  created_at: string;
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
type OperationView = "ACCOUNT_OPENING" | "CASH" | "TRANSFER" | "ADMIN";
type NavigationTab =
  | "HOME"
  | "DASHBOARD"
  | "OPERATIONS"
  | "LENDING"
  | "CUSTOMERS"
  | "AUDIT"
  | "RECONCILIATION";
type AuditView = "MY_ACTIVITY" | "AUDIT" | "NOTIFICATIONS";

const STAFF_SESSIONS_KEY = "shiva_staff_sessions";
const ACTIVE_STAFF_SESSION_KEY = "shiva_active_staff_session";
const TAB_QUERY_VALUES: Record<NavigationTab, string> = {
  HOME: "home",
  DASHBOARD: "accounts",
  OPERATIONS: "operations",
  LENDING: "lending",
  CUSTOMERS: "customers",
  AUDIT: "activity",
  RECONCILIATION: "reconciliation",
};

function readNavigationFromUrl(role?: Role): { tab: NavigationTab; auditView: AuditView } {
  const params = new URLSearchParams(window.location.search);
  const tabEntry = Object.entries(TAB_QUERY_VALUES).find(
    ([, value]) => value === params.get("tab"),
  );
  let tab = (tabEntry?.[0] as NavigationTab | undefined) ?? "HOME";
  const view = params.get("view");
  let auditView: AuditView =
    view === "staff"
      ? "AUDIT"
      : view === "notifications"
        ? "NOTIFICATIONS"
        : "MY_ACTIVITY";

  if (
    (role === "AUDITOR" && (tab === "OPERATIONS" || tab === "CUSTOMERS")) ||
    (role === "TELLER" && tab === "RECONCILIATION")
  ) {
    tab = "DASHBOARD";
  }
  if (role === "TELLER" && tab === "AUDIT" && auditView !== "MY_ACTIVITY") {
    auditView = "MY_ACTIVITY";
  }

  return { tab, auditView };
}

function storedStaffSessions(): StaffSession[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STAFF_SESSIONS_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed as StaffSession[] : [];
  } catch {
    return [];
  }

}

function setStoredStaffSessions(sessions: StaffSession[]) {
  window.localStorage.setItem(STAFF_SESSIONS_KEY, JSON.stringify(sessions));
}

function activeStaffSessionId() {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(ACTIVE_STAFF_SESSION_KEY)
    ?? window.localStorage.getItem(ACTIVE_STAFF_SESSION_KEY);
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/banking/${path}`, {
    ...options,
    cache: "no-store",
    headers: {
      ...(options.headers as Record<string, string> | undefined),
      ...(activeStaffSessionId() && activeStaffSessionId() !== "legacy"
        ? { "X-Banking-Session": activeStaffSessionId() as string }
        : {}),
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
  const [staffSessions, setStaffSessions] = useState<StaffSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionLoginOpen, setSessionLoginOpen] = useState(false);
  const [sessionUsername, setSessionUsername] = useState("");
  const [sessionPassword, setSessionPassword] = useState("");
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
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [accountKyc, setAccountKyc] = useState<Record<string, string>>({});
  const [operationView, setOperationView] = useState<OperationView>("ACCOUNT_OPENING");

  // Navigation tab
  const [activeTab, setActiveTab] = useState<NavigationTab>("HOME");
  const [loans, setLoans] = useState<Loan[]>([]);
  const [fixedDeposits, setFixedDeposits] = useState<FixedDeposit[]>([]);
  const [customerDetails, setCustomerDetails] = useState<CustomerDetails | null>(null);
  const [customerAccount, setCustomerAccount] = useState("");
  const [kycStatus, setKycStatus] = useState("PENDING");
  const [profilePhone, setProfilePhone] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profileAddress, setProfileAddress] = useState("");
  const [profileCity, setProfileCity] = useState("");
  const [profilePin, setProfilePin] = useState("");
  const [loanAccount, setLoanAccount] = useState("");
  const [loanType, setLoanType] = useState("PERSONAL");
  const [loanPrincipal, setLoanPrincipal] = useState("");
  const [loanRate, setLoanRate] = useState("12");
  const [loanTenure, setLoanTenure] = useState("12");
  const [fdAccount, setFdAccount] = useState("");
  const [fdPrincipal, setFdPrincipal] = useState("");
  const [fdRate, setFdRate] = useState("7");
  const [fdTenure, setFdTenure] = useState("365");
  const [interestAccount, setInterestAccount] = useState("");
  const [interestPeriod, setInterestPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [loanDetails, setLoanDetails] = useState<LoanDetails | null>(null);
  const [repaymentAmount, setRepaymentAmount] = useState("");
  const [repaymentMemo, setRepaymentMemo] = useState("");
  const [reverseTransaction, setReverseTransaction] = useState<Transaction | null>(null);
  const [reversalReason, setReversalReason] = useState("");
  const [staffPasswordTarget, setStaffPasswordTarget] = useState<StaffMember | null>(null);
  const [staffResetPassword, setStaffResetPassword] = useState("");

  // Cash operations state
  const [action, setAction] = useState<"DEPOSIT" | "WITHDRAWAL">("DEPOSIT");
  const [amount, setAmount] = useState("");
  const [moneyAccount, setMoneyAccount] = useState("");
  const [moneyMemo, setMoneyMemo] = useState("");
  const [accountAllowance, setAccountAllowance] = useState<AccountAllowance | null>(null);
  const [receipt, setReceipt] = useState<TransactionReceipt | null>(null);

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
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [customerCity, setCustomerCity] = useState("");
  const [customerPin, setCustomerPin] = useState("");
  const [customerAge, setCustomerAge] = useState("18");
  const [customerState, setCustomerState] = useState("");
  const [identityNumber, setIdentityNumber] = useState("");
  const [openingDeposit, setOpeningDeposit] = useState("2000.00");
  const [accountType, setAccountType] = useState<"SAVINGS" | "CURRENT" | "SALARY">("SAVINGS");

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
  const [auditOffset, setAuditOffset] = useState(0);
  const [notifications, setNotifications] = useState<NotificationLog[]>([]);
  const [auditView, setAuditView] = useState<AuditView>("MY_ACTIVITY");

  const loadDashboard = useCallback(async () => {
    const [nextSummary, nextAccounts, nextBranches, nextStates] = await Promise.all([
      api<Summary>("dashboard/summary"),
      api<{ items: Account[] }>("accounts?limit=50&offset=0"),
      api<Branch[]>("branches"),
      api<string[]>("metadata/india-states"),
    ]);
    setSummary(nextSummary);
    setAccounts(nextAccounts.items);
    setAccountKyc(Object.fromEntries(nextAccounts.items.map((account) => [
      account.account_number,
      account.kyc_status ?? "PENDING",
    ])));
    setBranches(nextBranches);
    setStates(nextStates);
  }, []);

  const loadStaff = useCallback(async () => {
    setStaffMembers(await api<StaffMember[]>("staff?limit=100&offset=0"));
  }, []);

  const loadProducts = useCallback(async () => {
    const [nextLoans, nextFixedDeposits] = await Promise.all([
      api<Loan[]>("loans?limit=50&offset=0"),
      api<FixedDeposit[]>("fixed-deposits?limit=50&offset=0"),
    ]);
    setLoans(nextLoans);
    setFixedDeposits(nextFixedDeposits);
  }, []);

  const loadActivityLogs = useCallback(async (
    scope: "mine" | "all",
    actionFilter = "",
    offset = 0,
  ) => {
    const params = new URLSearchParams({ limit: "100", offset: String(offset) });
    if (actionFilter.trim()) params.set("action", actionFilter.trim());
    const endpoint = scope === "mine" ? "staff/audit-logs" : "admin/audit-logs";
    const logs = await api<AuditLog[]>(`${endpoint}?${params}`);
    setAuditLogs(logs);
  }, []);

  const loadNotifications = useCallback(async () => {
    setNotifications(await api<NotificationLog[]>("admin/notifications?limit=50&offset=0"));
  }, []);

  function navigateToTab(tab: NavigationTab, view: AuditView = "MY_ACTIVITY") {
    const params = new URLSearchParams();
    if (tab !== "HOME") params.set("tab", TAB_QUERY_VALUES[tab]);
    if (tab === "AUDIT") {
      params.set(
        "view",
        view === "MY_ACTIVITY" ? "my-activity" : view === "AUDIT" ? "staff" : "notifications",
      );
    }
    const query = params.toString();
    window.history.pushState(null, "", query ? `/?${query}` : "/");
    setActiveTab(tab);
    if (tab === "AUDIT") setAuditView(view);
  }

  async function loadStaffWorkspace(currentStaff: Staff) {
    await Promise.all([loadDashboard(), loadProducts()]);
    if (currentStaff.role === "ADMIN") await loadStaff();
    else setStaffMembers([]);
    await loadActivityLogs("mine");
    if (currentStaff.role !== "ADMIN" && currentStaff.role !== "AUDITOR") {
      setNotifications([]);
    }
  }

  useEffect(() => {
    const savedSessions = storedStaffSessions();
    const selectedSession = activeStaffSessionId();
    setStaffSessions(savedSessions);
    if (selectedSession) setActiveSessionId(selectedSession);
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
    const syncNavigationFromUrl = () => {
      const { tab, auditView: view } = readNavigationFromUrl(staff?.role);
      setActiveTab(tab);
      setAuditView(view);
      if (!staff) return;
      if (tab === "AUDIT") {
        setAuditOffset(0);
        if (view === "MY_ACTIVITY") {
          void run(() => loadActivityLogs("mine", "", 0));
        } else if (view === "AUDIT") {
          void run(() => loadActivityLogs("all", "", 0));
        } else {
          void run(loadNotifications);
        }
      } else if (tab === "LENDING") {
        void run(loadProducts);
      }
    };
    window.addEventListener("popstate", syncNavigationFromUrl);
    return () => window.removeEventListener("popstate", syncNavigationFromUrl);
  }, [staff, loadActivityLogs, loadNotifications, loadProducts]);

  useEffect(() => {
    api<Staff>("auth/me")
      .then(async (currentStaff) => {
        const { tab, auditView: view } = readNavigationFromUrl(currentStaff.role);
        setActiveTab(tab);
        setAuditView(view);
        let selectedSession = activeStaffSessionId();
        if (!selectedSession) {
          selectedSession = "legacy";
          window.sessionStorage.setItem(ACTIVE_STAFF_SESSION_KEY, selectedSession);
          window.localStorage.setItem(ACTIVE_STAFF_SESSION_KEY, selectedSession);
        }
        const sessions = storedStaffSessions().filter((session) => session.id !== selectedSession);
        sessions.unshift({ id: selectedSession, staff: currentStaff });
        setStoredStaffSessions(sessions);
        setStaffSessions(sessions);
        setActiveSessionId(selectedSession);
        setStaff(currentStaff);
        try {
          await loadStaffWorkspace(currentStaff);
          if (tab === "AUDIT") {
            if (view === "MY_ACTIVITY") await loadActivityLogs("mine");
            else if (view === "AUDIT") await loadActivityLogs("all");
            else await loadNotifications();
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
  }, [loadDashboard, loadProducts, loadStaff, loadActivityLogs, loadNotifications]);

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

  async function authenticateStaff(loginUsername: string, loginPassword: string) {
    const sessionId = crypto.randomUUID();
    const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Banking-Session": sessionId },
        body: JSON.stringify({ username: loginUsername, password: loginPassword }),
      });
    const body = (await response.json()) as { detail?: string };
    if (!response.ok) throw new Error(body.detail ?? "Sign in failed.");
    window.sessionStorage.setItem(ACTIVE_STAFF_SESSION_KEY, sessionId);
    window.localStorage.setItem(ACTIVE_STAFF_SESSION_KEY, sessionId);
    const currentStaff = await api<Staff>("auth/me");
    const sessions = storedStaffSessions().filter((session) => session.id !== sessionId);
    sessions.unshift({ id: sessionId, staff: currentStaff });
    setStoredStaffSessions(sessions);
    setStaffSessions(sessions);
    setActiveSessionId(sessionId);
    setStaff(currentStaff);
    await loadStaffWorkspace(currentStaff);
    setNotice(`Signed in as ${currentStaff.full_name}.`);
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await authenticateStaff(username, password);
      setPassword("");
    });
  }

  async function addStaffSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await authenticateStaff(sessionUsername, sessionPassword);
      setSessionUsername("");
      setSessionPassword("");
      setSessionLoginOpen(false);
    });
  }

  async function switchStaffSession(sessionId: string) {
    if (sessionId === activeSessionId) return;
    const previousSession = activeSessionId;
    await run(async () => {
      window.sessionStorage.setItem(ACTIVE_STAFF_SESSION_KEY, sessionId);
      try {
        const currentStaff = await api<Staff>("auth/me");
        setActiveSessionId(sessionId);
        setStaff(currentStaff);
        navigateToTab("DASHBOARD");
        setSelectedAccount("");
        await loadStaffWorkspace(currentStaff);
        setNotice(`Switched to ${currentStaff.full_name}.`);
      } catch (cause) {
        if (previousSession) window.sessionStorage.setItem(ACTIVE_STAFF_SESSION_KEY, previousSession);
        else window.sessionStorage.removeItem(ACTIVE_STAFF_SESSION_KEY);
        throw cause;
      }
    });
  }

  async function searchAccounts(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const params = new URLSearchParams({ limit: "50", offset: "0" });
      if (query.trim()) params.set("q", query.trim());
      const result = await api<{ items: Account[] }>(`accounts?${params}`);
      setAccounts(result.items);
      setAccountKyc(Object.fromEntries(result.items.map((account) => [
        account.account_number,
        account.kyc_status ?? "PENDING",
      ])));
    });
  }

  async function selectAccount(accountNumber: string) {
    setSelectedAccount(accountNumber);
    setMoneyAccount(accountNumber);
    await run(async () => {
      const [rows, account] = await Promise.all([
        api<Transaction[]>(`accounts/${accountNumber}/transactions?limit=25&offset=0`),
        api<AccountAllowance>(`accounts/${accountNumber}`),
      ]);
      setTransactions(rows);
      setAccountAllowance(account);
      setAccountKyc((current) => ({ ...current, [accountNumber]: account.kyc_status }));
    });
  }

  async function refreshAccountAllowance(accountNumber: string) {
    if (!/^\d{10}$/.test(accountNumber)) {
      setAccountAllowance(null);
      return;
    }
    const details = await api<AccountAllowance>(`accounts/${accountNumber}`);
    setAccountAllowance(details);
    setAccountKyc((current) => ({ ...current, [accountNumber]: details.kyc_status }));
  }

  function kycStatusForAccount(accountNumber: string) {
    return accountKyc[accountNumber.trim()] ?? "UNKNOWN";
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
      if (end) params.set("end_at", new Date(`${end}T23:59:59.999`).toISOString());
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
      const result = await api<OperationResult>(`accounts/${moneyAccount}/${action === "DEPOSIT" ? "deposits" : "withdrawals"}`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ amount, memo: moneyMemo.trim() }),
      });
      setReceipt({
        transaction_id: result.transaction_id,
        type: action,
        amount,
        accounts: result.account_numbers,
        balances: result.balances,
        memo: moneyMemo.trim(),
        created_at: new Date().toISOString(),
      });
      setNotice(`${action === "DEPOSIT" ? "Deposit" : "Withdrawal"} of ₹${amount} posted successfully.`);
      setAmount("");
      setMoneyMemo("");
      await loadDashboard();
      await refreshAccountAllowance(moneyAccount);
      if (selectedAccount) await selectAccount(selectedAccount);
    });
  }

  async function submitTransfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const result = await api<OperationResult>("transfers", {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({
          sender_account: sender,
          receiver_account: receiver,
          amount: transferAmount,
          memo: transferMemo.trim(),
        }),
      });
      setReceipt({
        transaction_id: result.transaction_id,
        type: "TRANSFER",
        amount: transferAmount,
        accounts: result.account_numbers,
        balances: result.balances,
        memo: transferMemo.trim(),
        created_at: new Date().toISOString(),
      });
      setNotice(`Transfer of ₹${transferAmount} posted successfully.`);
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

  async function closeAccount(account: Account) {
    if (Number(account.balance) !== 0) {
      setError("An account can only be closed after its balance reaches ₹0.00.");
      return;
    }
    if (!window.confirm(`Permanently close zero-balance account ${account.account_number}?`)) return;
    await changeStatus(account.account_number, "CLOSED");
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
            email: customerEmail || null,
            address_line1: customerAddress || null,
            address_city: customerCity || null,
            address_pin: customerPin || null,
          },
          opening_deposit: openingDeposit,
          branch_ifsc: branchIfsc || branches[0]?.ifsc,
          account_type: accountType,
        }),
      });
      setCustomerFirst("");
      setCustomerLast("");
      setCustomerPhone("");
      setCustomerEmail("");
      setCustomerAddress("");
      setCustomerCity("");
      setCustomerPin("");
      setIdentityNumber("");
      setNotice("New account opened with KYC pending. Operations unlock after approval.");
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
      setNotice("Branch saved.");
      await loadDashboard();
    });
  }

  async function openCustomer(accountNumber: string) {
    await run(async () => {
      const account = await api<{
        customer: CustomerDetails;
        kyc_status: string;
      }>(`accounts/${accountNumber}`);
      setAccountKyc((current) => ({ ...current, [accountNumber]: account.kyc_status }));
      setCustomerDetails(account.customer);
      setCustomerAccount(accountNumber);
      setKycStatus(account.customer.kyc_status);
      setProfilePhone(account.customer.phone ?? "");
      setProfileEmail(account.customer.email ?? "");
      setProfileAddress(account.customer.address_line1 ?? "");
      setProfileCity(account.customer.address_city ?? "");
      setProfilePin(account.customer.address_pin ?? "");
    });
  }

  async function saveCustomerProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!customerDetails) return;
    await run(async () => {
      await api(`customers/${customerDetails.id}/profile`, {
        method: "PATCH",
        body: JSON.stringify({
          phone: profilePhone,
          email: profileEmail || null,
          address_line1: profileAddress || null,
          address_city: profileCity || null,
          address_pin: profilePin || null,
        }),
      });
      setNotice("Customer profile updated.");
      await openCustomer(customerAccount);
    });
  }

  async function saveKycStatus() {
    if (!customerDetails) return;
    await run(async () => {
      await api(`customers/${customerDetails.id}/kyc`, {
        method: "PATCH",
        body: JSON.stringify({ kyc_status: kycStatus }),
      });
      setCustomerDetails({ ...customerDetails, kyc_status: kycStatus });
      setAccountKyc((current) => ({ ...current, [customerAccount]: kycStatus }));
      setNotice(`KYC status updated to ${kycStatus}.`);
      await loadDashboard();
    });
  }

  async function submitLoan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const result = await api<{ emi: string }>("loans", {
        method: "POST",
        body: JSON.stringify({
          account_number: loanAccount,
          loan_type: loanType,
          principal_amount: loanPrincipal,
          interest_rate_annual: loanRate,
          tenure_months: Number(loanTenure),
        }),
      });
      setLoanPrincipal("");
      setNotice(`Loan application submitted. Estimated EMI: ₹${result.emi}.`);
      await Promise.all([loadProducts(), loadDashboard()]);
    });
  }

  async function submitFixedDeposit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api("fixed-deposits", {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({
          account_number: fdAccount,
          principal_amount: fdPrincipal,
          interest_rate_annual: fdRate,
          tenure_days: Number(fdTenure),
        }),
      });
      setFdPrincipal("");
      setNotice("Fixed deposit opened and ledger updated.");
      await Promise.all([loadProducts(), loadDashboard()]);
    });
  }

  async function closeFixedDeposit(fd: FixedDeposit, premature: boolean) {
    if (!window.confirm(
      premature
        ? `Close this FD before maturity (${fd.maturity_date})? A premature-closure adjustment may apply.`
        : `Close this FD at maturity (${fd.maturity_date})?`,
    )) return;
    await run(async () => {
      await api(`fixed-deposits/${fd.fd_id}/close`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ premature }),
      });
      setNotice(`Fixed deposit for ${fd.customer_name} closed.`);
      await Promise.all([loadProducts(), loadDashboard()]);
    });
  }

  async function postInterest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      await api(`accounts/${interestAccount}/interest?period_month=${encodeURIComponent(interestPeriod)}`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
      });
      setNotice(`Interest for ${interestPeriod} posted to ${interestAccount}.`);
      await Promise.all([loadDashboard(), selectAccount(interestAccount)]);
    });
  }

  async function openLoan(loanId: string) {
    await run(async () => {
      setLoanDetails(await api<LoanDetails>(`loans/${loanId}`));
      setRepaymentAmount("");
      setRepaymentMemo("");
    });
  }

  async function runLoanAction(loan: Loan, action: "APPROVE" | "REJECT" | "DISBURSE") {
    await run(async () => {
      await api(`loans/${loan.loan_id}/action`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ action }),
      });
      setNotice(`Loan ${action.toLowerCase()} action completed.`);
      await Promise.all([loadProducts(), loadDashboard()]);
    });
  }

  async function submitRepayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loanDetails) return;
    await run(async () => {
      await api(`loans/${loanDetails.loan_id}/repayments`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ amount: repaymentAmount, memo: repaymentMemo }),
      });
      setNotice("Loan repayment posted.");
      await Promise.all([loadProducts(), loadDashboard(), openLoan(loanDetails.loan_id)]);
    });
  }

  async function submitReversal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reverseTransaction) return;
    await run(async () => {
      await api(`transactions/${reverseTransaction.transaction_id}/reversals`, {
        method: "POST",
        headers: { "Idempotency-Key": operationKey() },
        body: JSON.stringify({ reason: reversalReason }),
      });
      setNotice("Transaction reversal posted as a new ledger transaction.");
      setReverseTransaction(null);
      setReversalReason("");
      await Promise.all([loadDashboard(), selectAccount(selectedAccount)]);
    });
  }

  async function updateStaffMember(member: StaffMember, change: { active?: boolean; role?: Role }) {
    await run(async () => {
      await api(`staff/${member.id}`, {
        method: "PATCH",
        body: JSON.stringify(change),
      });
      setNotice(`Staff account @${member.username} updated.`);
      await loadStaff();
    });
  }

  async function revokeStaffSession(member: StaffMember) {
    if (!window.confirm(`Sign out ${member.full_name} from their active device?`)) return;
    await run(async () => {
      await api(`staff/${member.id}/session-revoke`, { method: "POST" });
      setNotice(`Active session for @${member.username} was revoked.`);
      await loadStaff();
    });
  }

  async function resetStaffPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!staffPasswordTarget) return;
    await run(async () => {
      await api(`staff/${staffPasswordTarget.id}/password-reset`, {
        method: "POST",
        body: JSON.stringify({ password: staffResetPassword }),
      });
      setNotice(`Password reset for @${staffPasswordTarget.username}.`);
      setStaffPasswordTarget(null);
      setStaffResetPassword("");
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
      const sessionId = activeSessionId;
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: sessionId && sessionId !== "legacy" ? { "X-Banking-Session": sessionId } : {},
      });
      setStoredStaffSessions(staffSessions.filter((session) => session.id !== sessionId));
      window.sessionStorage.removeItem(ACTIVE_STAFF_SESSION_KEY);
      window.localStorage.removeItem(ACTIVE_STAFF_SESSION_KEY);
      setStaff(null);
      setActiveSessionId(null);
      setNotice("Password changed. Sign in again with your new password.");
    });
  }

  async function handleAuditFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      setAuditOffset(0);
      await loadActivityLogs(
        auditView === "AUDIT" ? "all" : "mine",
        auditSearch,
        0,
      );
    });
  }

  async function logout() {
    await run(async () => {
      const sessionId = activeSessionId;
      await api("auth/logout", {
        method: "POST",
      });
      const remainingSessions = staffSessions.filter((session) => session.id !== sessionId);
      setStoredStaffSessions(remainingSessions);
      setStaffSessions(remainingSessions);
      if (remainingSessions.length) {
        const nextSession = remainingSessions[0];
        window.sessionStorage.setItem(ACTIVE_STAFF_SESSION_KEY, nextSession.id);
        window.localStorage.setItem(ACTIVE_STAFF_SESSION_KEY, nextSession.id);
        setActiveSessionId(nextSession.id);
        const currentStaff = await api<Staff>("auth/me");
        setStaff(currentStaff);
        await loadStaffWorkspace(currentStaff);
      } else {
        window.sessionStorage.removeItem(ACTIVE_STAFF_SESSION_KEY);
        window.localStorage.removeItem(ACTIVE_STAFF_SESSION_KEY);
        setActiveSessionId(null);
        setStaff(null);
        setSummary(null);
        setAccounts([]);
        setTransactions([]);
      }
    });
  }

  const filteredAccounts = accounts.filter((acc) => {
    if (statusFilter === "ALL") return true;
    return acc.status === statusFilter;
  });
  const verifiedAccounts = filteredAccounts.filter(
    (account) => account.kyc_status === "VERIFIED",
  );
  const unverifiedAccounts = filteredAccounts.filter(
    (account) => account.kyc_status !== "VERIFIED",
  );
  const renderAccountTable = (
    accountList: Account[],
    emptyMessage: string,
    role: Role,
  ) => (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Account</th>
            <th>Customer</th>
            <th>IFSC</th>
            <th>Status</th>
            <th>KYC</th>
            <th>Balance</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {accountList.map((account) => (
            <tr key={account.account_number}>
              <td className="mono">{account.account_number}</td>
              <td>{account.customer_name}</td>
              <td className="mono">{account.ifsc}</td>
              <td>
                <span className={`status status-${account.status.toLowerCase()}`}>
                  {account.status}
                </span>
              </td>
              <td>
                <span className={`status kyc-${(account.kyc_status ?? "PENDING").toLowerCase()}`}>
                  {account.kyc_status ?? "PENDING"}
                </span>
              </td>
              <td><strong>₹{account.balance}</strong></td>
              <td className="row-actions">
                <button
                  className="text-button"
                  disabled={account.kyc_status !== "VERIFIED"}
                  onClick={() => selectAccount(account.account_number)}
                >
                  Activity
                </button>
                <button
                  className="text-button"
                  disabled={account.kyc_status !== "VERIFIED"}
                  onClick={() => openStatementModal(account.account_number)}
                >
                  Statement
                </button>
                {role !== "AUDITOR" && (
                  <button
                    className="text-button"
                    onClick={() => {
                      navigateToTab("CUSTOMERS");
                      openCustomer(account.account_number);
                    }}
                  >
                    Customer
                  </button>
                )}
                {role === "ADMIN" && account.status !== "CLOSED" && (
                  <>
                    <button
                      className="text-button"
                      disabled={account.kyc_status !== "VERIFIED"}
                      onClick={() =>
                        changeStatus(
                          account.account_number,
                          account.status === "FROZEN" ? "ACTIVE" : "FROZEN"
                        )
                      }
                    >
                      {account.status === "FROZEN" ? "Unfreeze" : "Freeze"}
                    </button>
                    <button
                      className="text-button"
                      disabled={account.kyc_status !== "VERIFIED"}
                      onClick={() => closeAccount(account)}
                    >
                      Close
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
          {accountList.length === 0 && (
            <tr>
              <td colSpan={7} className="empty">{emptyMessage}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );

  if (!staff) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <div className="brand-mark">B</div>
          <p className="eyebrow">BANKING OPERATIONS</p>
          <h1>Secure Staff Sign In</h1>
          <p className="muted">Sign in to your secure staff workspace.</p>
          {error && <p className="alert error">{error}</p>}
          {notice && <p className="alert success">{notice}</p>}
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
            <strong>SHIVA Banking</strong>
            <span>Operations workspace</span>
          </div>
        </div>
        <div className="staff-menu">
          <select className="session-select" aria-label="Active staff session" value={activeSessionId ?? ""} onChange={(event) => switchStaffSession(event.target.value)}>
            {staffSessions.map((session) => <option key={session.id} value={session.id}>{session.staff.full_name} · {session.staff.role}</option>)}
          </select>
          <button className="button-secondary add-session-button" onClick={() => setSessionLoginOpen(true)} disabled={busy} title="Sign in another staff account">
            <UserRoundPlus size={16} /> Add login
          </button>
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
            Sign out this session
          </button>
        </div>
      </header>

      <div className="app-layout">
        <aside className="sidebar" aria-label="Main navigation">
          <div className="sidebar-brand">
            <span className="sidebar-brand-icon"><Landmark size={17} /></span>
            <span className="sidebar-brand-copy">
              <strong>SHIVA BANK</strong>
              <small>STAFF PORTAL</small>
            </span>
            <span className="sidebar-live"><span /> LIVE</span>
          </div>
          <p className="sidebar-label">WORKSPACE</p>
          <nav className="menu-list">
            <button className={`menu-item ${activeTab === "HOME" ? "active" : ""}`} aria-current={activeTab === "HOME" ? "page" : undefined} onClick={() => navigateToTab("HOME")}><LayoutDashboard size={18} /><span>Home</span></button>
            <button className={`menu-item ${activeTab === "DASHBOARD" ? "active" : ""}`} aria-current={activeTab === "DASHBOARD" ? "page" : undefined} onClick={() => navigateToTab("DASHBOARD")}><UsersRound size={18} /><span>Accounts</span></button>
            {staff.role !== "AUDITOR" && <button className={`menu-item ${activeTab === "OPERATIONS" ? "active" : ""}`} aria-current={activeTab === "OPERATIONS" ? "page" : undefined} onClick={() => navigateToTab("OPERATIONS")}><ChartNoAxesColumn size={18} /><span>Operations</span></button>}
            <button className={`menu-item ${activeTab === "LENDING" ? "active" : ""}`} aria-current={activeTab === "LENDING" ? "page" : undefined} onClick={() => { navigateToTab("LENDING"); run(loadProducts); }}><Landmark size={18} /><span>Loans & deposits</span></button>
            {staff.role !== "AUDITOR" && <button className={`menu-item ${activeTab === "CUSTOMERS" ? "active" : ""}`} aria-current={activeTab === "CUSTOMERS" ? "page" : undefined} onClick={() => navigateToTab("CUSTOMERS")}><UsersRound size={18} /><span>Customer services</span></button>}
            <button className={`menu-item ${activeTab === "AUDIT" && auditView === "MY_ACTIVITY" ? "active" : ""}`} aria-current={activeTab === "AUDIT" && auditView === "MY_ACTIVITY" ? "page" : undefined} onClick={() => { navigateToTab("AUDIT", "MY_ACTIVITY"); run(() => loadActivityLogs("mine")); }}><ShieldCheck size={18} /><span>My activity</span></button>
            {(staff.role === "ADMIN" || staff.role === "AUDITOR") && <button className={`menu-item ${activeTab === "AUDIT" && auditView === "AUDIT" ? "active" : ""}`} aria-current={activeTab === "AUDIT" && auditView === "AUDIT" ? "page" : undefined} onClick={() => { navigateToTab("AUDIT", "AUDIT"); run(() => loadActivityLogs("all")); }}><UsersRound size={18} /><span>Staff audit</span></button>}
            {(staff.role === "ADMIN" || staff.role === "AUDITOR") && <button className={`menu-item ${activeTab === "RECONCILIATION" ? "active" : ""}`} aria-current={activeTab === "RECONCILIATION" ? "page" : undefined} onClick={() => navigateToTab("RECONCILIATION")}><Scale size={18} /><span>Reconciliation</span></button>}
          </nav>
          <div className="sidebar-role">
            <span className="sidebar-role-icon"><ShieldCheck size={17} /></span>
            <span className="sidebar-role-copy">
              <strong>{staff.role} ACCESS</strong>
              <small>Secure staff workspace</small>
            </span>
          </div>
        </aside>
        <div className="content-stage">
      <section className="page-heading">
        <div>
          <p className="eyebrow">BANKING OPERATIONS</p>
          <h1>{activeTab === "HOME" ? `Welcome, ${staff.full_name}` : activeTab === "DASHBOARD" ? "Accounts overview" : activeTab === "OPERATIONS" ? "Banking operations" : activeTab === "LENDING" ? "Loans & deposits" : activeTab === "CUSTOMERS" ? "Customer services" : activeTab === "AUDIT" ? auditView === "MY_ACTIVITY" ? "My activity" : auditView === "AUDIT" ? "Staff activity" : "Notifications" : "Reconciliation"}</h1>
          <p className="muted">{activeTab === "HOME" ? "Choose a service to get started." : "Secure staff workspace · actions are recorded for review."}</p>
        </div>
        <button className="button-secondary" onClick={() => run(loadDashboard)} disabled={busy}>
          Refresh data
        </button>
      </section>

      {error && <p className="alert error">{error}</p>}
      {notice && <p className="alert success">{notice}</p>}

      {activeTab === "HOME" && (
        <section className="service-picker">
          <div className="service-picker-heading">
            <p className="eyebrow">QUICK ACCESS</p>
            <h2>What would you like to do?</h2>
            <p className="muted">Choose a task. Customer functions remain locked until KYC is approved.</p>
          </div>
          <div className="service-grid">
            <button className="service-card" onClick={() => navigateToTab("DASHBOARD")}>
              <span className="service-icon"><UsersRound size={21} /></span>
              <strong>Find an account</strong>
              <span>Search accounts, review status and open statements.</span>
              <span className="service-link">Open accounts <span aria-hidden="true">→</span></span>
            </button>
            {staff.role !== "AUDITOR" && (
              <button className="service-card" onClick={() => navigateToTab("OPERATIONS")}>
                <span className="service-icon"><ChartNoAxesColumn size={21} /></span>
                <strong>Open account or transact</strong>
                <span>Create a customer account, take deposits or manage transfers.</span>
                <span className="service-link">Open operations <span aria-hidden="true">→</span></span>
              </button>
            )}
            {staff.role !== "AUDITOR" && (
              <button className="service-card" onClick={() => navigateToTab("CUSTOMERS")}>
                <span className="service-icon"><ShieldCheck size={21} /></span>
                <strong>Review customer KYC</strong>
                <span>Check customer information and manage verification status.</span>
                <span className="service-link">Review KYC <span aria-hidden="true">→</span></span>
              </button>
            )}
            <button className="service-card" onClick={() => { navigateToTab("LENDING"); run(loadProducts); }}>
              <span className="service-icon"><Landmark size={21} /></span>
              <strong>Loans & fixed deposits</strong>
              <span>Review lending requests and deposit products.</span>
              <span className="service-link">Open products <span aria-hidden="true">→</span></span>
            </button>
            <button className="service-card" onClick={() => { navigateToTab("AUDIT", "MY_ACTIVITY"); run(() => loadActivityLogs("mine")); }}>
                <span className="service-icon"><Scale size={21} /></span>
                <strong>My activity</strong>
                <span>Review your own sign-ins, account operations and changes.</span>
                <span className="service-link">Open activity <span aria-hidden="true">→</span></span>
            </button>
          </div>
        </section>
      )}

      {(activeTab === "DASHBOARD" || activeTab === "OPERATIONS") && (
        <>
          {activeTab === "DASHBOARD" && <>
          <section className="metric-grid">
            <article className="metric-card">
              <span>Total accounts</span>
              <strong>{summary?.accounts.total ?? "—"}</strong>
              <small>{summary?.accounts.active ?? 0} active accounts</small>
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
            <article className="metric-card">
              <span>Loans outstanding</span>
              <strong>₹{summary?.loans?.outstanding ?? "0.00"}</strong>
              <small>{summary?.loans?.active ?? 0} active · {summary?.loans?.applied ?? 0} awaiting review</small>
            </article>
            <article className="metric-card">
              <span>Active fixed deposits</span>
              <strong>{summary?.fixed_deposits?.active ?? 0}</strong>
              <small>₹{summary?.fixed_deposits?.total_value ?? "0.00"} principal</small>
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
            <section className="account-kyc-group">
              <div className="panel-heading">
                <div>
                  <h2>Verified KYC accounts</h2>
                  <p className="muted">Accounts with approved customer verification.</p>
                </div>
                <span className="status status-active">{verifiedAccounts.length} accounts</span>
              </div>
              {renderAccountTable(verifiedAccounts, "No verified accounts match the current filters.", staff.role)}
            </section>
            <section className="account-kyc-group">
              <div className="panel-heading">
                <div>
                  <h2>KYC not verified</h2>
                  <p className="muted">Pending and rejected customer verifications.</p>
                </div>
                <span className="status kyc-pending">{unverifiedAccounts.length} accounts</span>
              </div>
              {renderAccountTable(unverifiedAccounts, "No unverified accounts match the current filters.", staff.role)}
            </section>
          </section>

          {selectedAccount && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Recent activity</h2>
                  <p className="muted">Recent activity for account {selectedAccount}</p>
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
                        <td className="row-actions">
                          <span className="status">{transaction.status}</span>
                          {staff.role === "ADMIN" &&
                            transaction.status === "POSTED" &&
                            transaction.type !== "REVERSAL" && (
                              <button
                                className="text-button"
                                onClick={() => setReverseTransaction(transaction)}
                              >
                                Reverse
                              </button>
                            )}
                        </td>
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
          </>}

          {activeTab === "OPERATIONS" && (staff.role === "ADMIN" || staff.role === "TELLER") && (
            <>
            <nav className="operation-selector" aria-label="Choose banking operation">
              <button className={`pill-btn ${operationView === "ACCOUNT_OPENING" ? "active" : ""}`} aria-pressed={operationView === "ACCOUNT_OPENING"} onClick={() => setOperationView("ACCOUNT_OPENING")}>Open account</button>
              <button className={`pill-btn ${operationView === "CASH" ? "active" : ""}`} aria-pressed={operationView === "CASH"} onClick={() => setOperationView("CASH")}>Deposit / withdraw</button>
              <button className={`pill-btn ${operationView === "TRANSFER" ? "active" : ""}`} aria-pressed={operationView === "TRANSFER"} onClick={() => setOperationView("TRANSFER")}>Transfer</button>
              {staff.role === "ADMIN" && <button className={`pill-btn ${operationView === "ADMIN" ? "active" : ""}`} aria-pressed={operationView === "ADMIN"} onClick={() => setOperationView("ADMIN")}>Administration</button>}
            </nav>
            <section className="work-grid operation-work-grid">
              <article className="panel" hidden={operationView !== "ACCOUNT_OPENING"}>
                <h2>Open an account</h2>
                <p className="muted">Identity numbers are cryptographically fingerprinted before saving.</p>
                <form className="stack" onSubmit={openAccount}>
                  <div className="form-section-label">Personal details</div>
                  <div className="form-fields-grid">
                  <label>First name<input autoComplete="given-name" value={customerFirst} onChange={(event) => setCustomerFirst(event.target.value)} required /></label>
                  <label>Last name<input autoComplete="family-name" value={customerLast} onChange={(event) => setCustomerLast(event.target.value)} required /></label>
                  <label>Phone<input autoComplete="tel" inputMode="tel" value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} required /></label>
                  <label>Email address<input autoComplete="email" type="email" value={customerEmail} onChange={(event) => setCustomerEmail(event.target.value)} /></label>
                  <label>Age<input type="number" min={18} max={110} value={customerAge} onChange={(event) => setCustomerAge(event.target.value)} required /></label>
                  <label>State / union territory<select value={customerState} onChange={(event) => setCustomerState(event.target.value)} required><option value="">Select a state</option>{states.map((state) => <option key={state} value={state}>{state}</option>)}</select></label>
                  <label>Identity number (12-digit)<input inputMode="numeric" pattern="[0-9]{12}" value={identityNumber} onChange={(event) => setIdentityNumber(event.target.value)} required /></label>
                  </div>
                  <div className="form-section-label">Address details</div>
                  <div className="form-fields-grid">
                  <label className="field-full">Address<input autoComplete="street-address" value={customerAddress} onChange={(event) => setCustomerAddress(event.target.value)} required /></label>
                  <label>City / district<input autoComplete="address-level2" value={customerCity} onChange={(event) => setCustomerCity(event.target.value)} required /></label>
                  <label>PIN code<input autoComplete="postal-code" inputMode="numeric" pattern="[0-9]{6}" value={customerPin} onChange={(event) => setCustomerPin(event.target.value)} required /></label>
                  </div>
                  <div className="form-section-label">Account setup</div>
                  <label>Branch<select value={branchIfsc} onChange={(event) => setBranchIfsc(event.target.value)} required>{branches.map((branch) => <option key={branch.ifsc} value={branch.ifsc}>{branch.name} · {branch.ifsc}</option>)}</select></label>
                  <label>Account type<select value={accountType} onChange={(event) => setAccountType(event.target.value as "SAVINGS" | "CURRENT" | "SALARY")}><option value="SAVINGS">Savings</option><option value="CURRENT">Current</option><option value="SALARY">Salary</option></select></label>
                  <label>Opening deposit (₹, min 2000)<input inputMode="decimal" value={openingDeposit} onChange={(event) => setOpeningDeposit(event.target.value)} required /></label>
                  <div className="kyc-notice">New accounts start with KYC pending. Deposits, withdrawals, transfers and other account services stay disabled until an administrator approves KYC.</div>
                  <button disabled={busy}>Create account</button>
                </form>
              </article>

              <article className="panel" hidden={operationView !== "CASH"}>
                <h2>Cash operation</h2>
                <p className="muted">Post a deposit or withdrawal with an optional memo & idempotency.</p>
                <form className="stack" onSubmit={submitMoney}>
                  <label>Operation
                    <select value={action} onChange={(event) => setAction(event.target.value as "DEPOSIT" | "WITHDRAWAL")}>
                      <option value="DEPOSIT">Deposit</option>
                      <option value="WITHDRAWAL">Withdrawal</option>
                    </select>
                  </label>
                  <label>Account number<input inputMode="numeric" pattern="[0-9]{10}" value={moneyAccount} onChange={(event) => { setMoneyAccount(event.target.value); setAccountAllowance(null); }} onBlur={() => run(() => refreshAccountAllowance(moneyAccount))} placeholder="10-digit account number" required /></label>
                  {moneyAccount && kycStatusForAccount(moneyAccount) !== "VERIFIED" && <p className="kyc-notice">KYC {kycStatusForAccount(moneyAccount).toLowerCase()}. Account services are locked until approval.</p>}
                  {action === "WITHDRAWAL" && accountAllowance && (
                    <div className="daily-limit" aria-live="polite">
                      <span>Daily withdrawal cap</span><strong>₹{accountAllowance.daily_withdrawal_limit}</strong>
                      <span>Used today</span><strong>₹{accountAllowance.daily_withdrawn_today}</strong>
                      <span>Remaining</span><strong>₹{accountAllowance.daily_withdrawal_remaining}</strong>
                    </div>
                  )}
                  <label>Amount (₹)<input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" required /></label>
                  <label>Remark / Note (Optional)<input value={moneyMemo} onChange={(event) => setMoneyMemo(event.target.value)} placeholder="e.g. Salary, Monthly rent, Cash deposit" /></label>
                  <button disabled={busy || kycStatusForAccount(moneyAccount) !== "VERIFIED"}>Post {action.toLowerCase()}</button>
                </form>
              </article>

              <article className="panel" hidden={operationView !== "TRANSFER"}>
                <h2>Transfer funds</h2>
                <p className="muted">Atomic double-entry transfer between active accounts.</p>
                <form className="stack" onSubmit={submitTransfer}>
                  <label>From account<input inputMode="numeric" pattern="[0-9]{10}" value={sender} onChange={(event) => { setSender(event.target.value); setAccountAllowance(null); }} onBlur={() => run(() => refreshAccountAllowance(sender))} placeholder="Sender 10-digit account" required /></label>
                  {sender && kycStatusForAccount(sender) !== "VERIFIED" && <p className="kyc-notice">Sender KYC {kycStatusForAccount(sender).toLowerCase()}. Transfer is locked until approval.</p>}
                  {accountAllowance && (
                    <div className="daily-limit" aria-live="polite">
                      <span>Daily outgoing cap</span><strong>₹{accountAllowance.daily_withdrawal_limit}</strong>
                      <span>Used today</span><strong>₹{accountAllowance.daily_withdrawn_today}</strong>
                      <span>Remaining</span><strong>₹{accountAllowance.daily_withdrawal_remaining}</strong>
                    </div>
                  )}
                  <label>To account<input inputMode="numeric" pattern="[0-9]{10}" value={receiver} onChange={(event) => setReceiver(event.target.value)} onBlur={() => run(() => refreshAccountAllowance(receiver))} placeholder="Receiver 10-digit account" required /></label>
                  {receiver && kycStatusForAccount(receiver) !== "VERIFIED" && <p className="kyc-notice">Receiver KYC {kycStatusForAccount(receiver).toLowerCase()}. Transfer is locked until approval.</p>}
                  <label>Amount (₹)<input inputMode="decimal" value={transferAmount} onChange={(event) => setTransferAmount(event.target.value)} placeholder="0.00" required /></label>
                  <label>Transfer remark (Optional)<input value={transferMemo} onChange={(event) => setTransferMemo(event.target.value)} placeholder="e.g. Invoice #203, Vendor payment" /></label>
                  <button disabled={busy || kycStatusForAccount(sender) !== "VERIFIED" || kycStatusForAccount(receiver) !== "VERIFIED"}>Submit secure transfer</button>
                </form>
              </article>

              {staff.role === "ADMIN" && (
                <article className="panel" hidden={operationView !== "ADMIN"}>
                  <h2>Add a branch</h2>
                  <p className="muted">Manage branch codes for new accounts.</p>
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

          {staff.role === "ADMIN" && operationView === "ADMIN" && (
            <section className="work-grid">
              <article className="panel">
                <h2>Create staff account</h2>
                <p className="muted">Assign role permissions for banking tellers or auditors.</p>
                <form className="stack" onSubmit={createStaff}>
                  <label>Full name<input value={newName} onChange={(event) => setNewName(event.target.value)} required /></label>
                  <label>Username<input minLength={3} value={newUsername} onChange={(event) => setNewUsername(event.target.value)} required /></label>
                  <label>Role<select value={newRole} onChange={(event) => setNewRole(event.target.value as "TELLER" | "AUDITOR")}><option value="TELLER">Teller</option><option value="AUDITOR">Auditor</option></select></label>
                  <label>Initial password<input type="password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="At least 12 characters" required /></label>
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
                        <span>@{member.username} · {member.active ? "Active" : "Inactive"}</span>
                        <span>{member.signed_in ? "Currently signed in" : "Signed out"} · last login {member.last_login_at ? new Date(member.last_login_at).toLocaleString() : "Never"}</span>
                      </div>
                      <div className="staff-controls">
                        <select
                          aria-label={`Role for ${member.username}`}
                          value={member.role}
                          disabled={busy || member.id === staff.id}
                          onChange={(event) => updateStaffMember(member, { role: event.target.value as Role })}
                        >
                          <option value="ADMIN">Admin</option><option value="TELLER">Teller</option><option value="AUDITOR">Auditor</option>
                        </select>
                        <button className="text-button" disabled={busy || member.id === staff.id} onClick={() => updateStaffMember(member, { active: !member.active })}>
                          {member.active ? "Deactivate" : "Activate"}
                        </button>
                        <button className="text-button" disabled={busy} onClick={() => setStaffPasswordTarget(member)}>Reset password</button>
                        {member.signed_in && <button className="text-button" disabled={busy} onClick={() => revokeStaffSession(member)}>Sign out device</button>}
                      </div>
                    </div>
                  ))}
                  {staffMembers.length === 0 && <p className="empty">No staff accounts found.</p>}
                </div>
              </article>
            </section>
          )}
        </>
      )}
        </>
      )}

      {activeTab === "LENDING" && (
        <>
          {staff.role !== "AUDITOR" && (
            <section className="work-grid">
              <article className="panel">
                <h2>New loan application</h2>
                <p className="muted">Link an account, enter terms, then an admin can approve or reject the application.</p>
                <form className="stack" onSubmit={submitLoan}>
                  <label>Customer account number<input inputMode="numeric" pattern="[0-9]{10}" value={loanAccount} onChange={(event) => setLoanAccount(event.target.value)} onBlur={() => run(() => refreshAccountAllowance(loanAccount))} required /></label>
                  {loanAccount && kycStatusForAccount(loanAccount) !== "VERIFIED" && <p className="kyc-notice">KYC {kycStatusForAccount(loanAccount).toLowerCase()}. Loan services are locked until approval.</p>}
                  <label>Loan product<select value={loanType} onChange={(event) => setLoanType(event.target.value)}><option value="PERSONAL">Personal</option><option value="HOME">Home</option><option value="VEHICLE">Vehicle</option><option value="EDUCATION">Education</option><option value="GOLD">Gold</option></select></label>
                  <label>Principal (₹)<input inputMode="decimal" value={loanPrincipal} onChange={(event) => setLoanPrincipal(event.target.value)} required /></label>
                  <label>Annual interest rate (%)<input type="number" min="0.01" max="36" step="0.01" value={loanRate} onChange={(event) => setLoanRate(event.target.value)} required /></label>
                  <label>Tenure (months)<input type="number" min="1" max="360" value={loanTenure} onChange={(event) => setLoanTenure(event.target.value)} required /></label>
                  <button disabled={busy || kycStatusForAccount(loanAccount) !== "VERIFIED"}>Submit loan application</button>
                </form>
              </article>
              <article className="panel">
                <h2>Open fixed deposit</h2>
                <p className="muted">FD principal is transferred from the selected active account into the deposit ledger.</p>
                <form className="stack" onSubmit={submitFixedDeposit}>
                  <label>Funding account number<input inputMode="numeric" pattern="[0-9]{10}" value={fdAccount} onChange={(event) => setFdAccount(event.target.value)} onBlur={() => run(() => refreshAccountAllowance(fdAccount))} required /></label>
                  {fdAccount && kycStatusForAccount(fdAccount) !== "VERIFIED" && <p className="kyc-notice">KYC {kycStatusForAccount(fdAccount).toLowerCase()}. Fixed-deposit services are locked until approval.</p>}
                  <label>Principal (₹)<input inputMode="decimal" value={fdPrincipal} onChange={(event) => setFdPrincipal(event.target.value)} required /></label>
                  <label>Annual interest rate (%)<input type="number" min="0.01" max="15" step="0.01" value={fdRate} onChange={(event) => setFdRate(event.target.value)} required /></label>
                  <label>Tenure (days)<input type="number" min="7" max="3650" value={fdTenure} onChange={(event) => setFdTenure(event.target.value)} required /></label>
                  <button disabled={busy || kycStatusForAccount(fdAccount) !== "VERIFIED"}>Open fixed deposit</button>
                </form>
              </article>
              {staff.role === "ADMIN" && (
                <article className="panel">
                  <h2>Post monthly savings interest</h2>
                  <p className="muted">Posts interest once per account and month. Duplicate periods are rejected by the ledger.</p>
                  <form className="stack" onSubmit={postInterest}>
                    <label>Savings / salary account<input inputMode="numeric" pattern="[0-9]{10}" value={interestAccount} onChange={(event) => setInterestAccount(event.target.value)} required /></label>
                    <label>Interest month<input type="month" value={interestPeriod} onChange={(event) => setInterestPeriod(event.target.value)} required /></label>
                    <button disabled={busy}>Post interest</button>
                  </form>
                </article>
              )}
            </section>
          )}

          <section className="panel">
            <div className="panel-heading">
              <div><h2>Loan portfolio</h2><p className="muted">Applications, approvals, disbursements and repayments.</p></div>
              <button className="button-secondary" disabled={busy} onClick={() => run(loadProducts)}>Refresh products</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Customer</th><th>Type</th><th>Status</th><th>Principal</th><th>Outstanding</th><th>EMI</th><th>Rate / Tenure</th><th>Actions</th></tr></thead>
                <tbody>
                  {loans.map((loan) => (
                    <tr key={loan.loan_id}>
                      <td>{loan.customer_name}</td><td>{loan.loan_type}</td><td><span className="status">{loan.status}</span><br /><span className={`status kyc-${loan.kyc_status.toLowerCase()}`}>{loan.kyc_status}</span></td>
                      <td>₹{loan.principal}</td><td>₹{loan.outstanding}</td><td>₹{loan.emi}</td>
                      <td>{loan.interest_rate_annual}% · {loan.tenure_months} mo</td>
                      <td className="row-actions">
                        <button className="text-button" disabled={loan.kyc_status !== "VERIFIED"} onClick={() => openLoan(loan.loan_id)}>Details / repay</button>
                        {staff.role === "ADMIN" && loan.kyc_status === "VERIFIED" && loan.status === "APPLIED" && (
                          <>
                            <button className="text-button" disabled={busy} onClick={() => runLoanAction(loan, "APPROVE")}>Approve</button>
                            <button className="text-button" disabled={busy} onClick={() => runLoanAction(loan, "REJECT")}>Reject</button>
                          </>
                        )}
                        {staff.role === "ADMIN" && loan.kyc_status === "VERIFIED" && loan.status === "APPROVED" && (
                          <button className="text-button" disabled={busy} onClick={() => runLoanAction(loan, "DISBURSE")}>Disburse</button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {loans.length === 0 && <tr><td colSpan={8} className="empty">No loan applications found.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading"><div><h2>Fixed deposit portfolio</h2><p className="muted">Maturity projections use simple interest as configured by the banking service.</p></div></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Customer</th><th>Status</th><th>Principal</th><th>Rate</th><th>Tenure</th><th>Maturity date</th><th>Projected maturity</th><th>Actions</th></tr></thead>
                <tbody>
                  {fixedDeposits.map((fd) => (
                    <tr key={fd.fd_id}>
                      <td>{fd.customer_name}</td><td><span className="status">{fd.status}</span><br /><span className={`status kyc-${fd.kyc_status.toLowerCase()}`}>{fd.kyc_status}</span></td>
                      <td>₹{fd.principal}</td><td>{fd.interest_rate_annual}%</td><td>{fd.tenure_days} days</td>
                      <td>{fd.maturity_date}</td><td>₹{fd.maturity_amount}</td>
                      <td className="row-actions">
                        {staff.role === "ADMIN" && fd.kyc_status === "VERIFIED" && fd.status === "ACTIVE" && (
                          <>
                            <button className="text-button" disabled={busy || fd.maturity_date > new Date().toISOString().slice(0, 10)} onClick={() => closeFixedDeposit(fd, false)}>Close at maturity</button>
                            <button className="text-button" disabled={busy} onClick={() => closeFixedDeposit(fd, true)}>Premature close</button>
                          </>
                        )}
                        {fd.status !== "ACTIVE" && "—"}
                      </td>
                    </tr>
                  ))}
                  {fixedDeposits.length === 0 && <tr><td colSpan={8} className="empty">No fixed deposits found.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {activeTab === "CUSTOMERS" && staff.role !== "AUDITOR" && (
        <>
          <section className="panel">
            <div className="panel-heading">
              <div><h2>Customer records & KYC</h2><p className="muted">Select an account to view or update the associated customer record.</p></div>
              <form className="search-form" onSubmit={searchAccounts}>
                <input aria-label="Search customers" placeholder="Search name or account number" value={query} onChange={(event) => setQuery(event.target.value)} />
                <button className="button-secondary" disabled={busy}>Search</button>
              </form>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Account</th><th>Customer</th><th>Account type</th><th>KYC status</th><th>Action</th></tr></thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.account_number}>
                      <td className="mono">{account.account_number}</td><td>{account.customer_name}</td><td>{account.account_type ?? "SAVINGS"}</td>
                      <td><span className={`status kyc-${(account.kyc_status ?? "PENDING").toLowerCase()}`}>{account.kyc_status ?? "PENDING"}</span></td>
                      <td><button className="text-button" onClick={() => openCustomer(account.account_number)}>Manage customer</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {customerDetails && (
            <section className="work-grid">
              <article className="panel">
                <h2>{customerDetails.first_name} {customerDetails.last_name}</h2>
                <p className="muted">Customer ID: <span className="mono">{customerDetails.id}</span> · Account {customerAccount}</p>
                <div className="inline-form">
                  <label>KYC status<select value={kycStatus} onChange={(event) => setKycStatus(event.target.value)} disabled={staff.role !== "ADMIN" || customerDetails.kyc_status === "REJECTED"}><option value="PENDING">Pending</option><option value="VERIFIED">Verified</option><option value="REJECTED">Rejected</option></select></label>
                  {staff.role === "ADMIN" && customerDetails.kyc_status !== "REJECTED" && <button disabled={busy} onClick={saveKycStatus}>Save KYC status</button>}
                  {customerDetails.kyc_status === "REJECTED" && <p className="kyc-notice kyc-notice-rejected">Rejected KYC is locked. No further customer or account action is available.</p>}
                  {customerDetails.kyc_status === "PENDING" && <p className="kyc-notice">Pending KYC permits review only. Account operations unlock after approval.</p>}
                </div>
              </article>
              <article className="panel">
                <h2>Update customer profile</h2>
                <form className="stack" onSubmit={saveCustomerProfile}>
                  <fieldset disabled={busy || customerDetails.kyc_status !== "VERIFIED"}>
                  <label>Phone<input inputMode="tel" value={profilePhone} onChange={(event) => setProfilePhone(event.target.value)} required /></label>
                  <label>Email<input type="email" value={profileEmail} onChange={(event) => setProfileEmail(event.target.value)} /></label>
                  <label>Address<input value={profileAddress} onChange={(event) => setProfileAddress(event.target.value)} /></label>
                  <label>City<input value={profileCity} onChange={(event) => setProfileCity(event.target.value)} /></label>
                  <label>PIN code<input value={profilePin} onChange={(event) => setProfilePin(event.target.value)} /></label>
                  <button disabled={busy}>Save customer profile</button>
                  </fieldset>
                  {customerDetails.kyc_status !== "VERIFIED" && <p className="muted">Customer details are read-only until KYC is approved.</p>}
                </form>
              </article>
            </section>
          )}
        </>
      )}

      {activeTab === "AUDIT" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>{auditView === "MY_ACTIVITY" ? "My activity" : auditView === "AUDIT" ? "Staff activity & audit trail" : "Notification delivery log"}</h2>
              <p className="muted">{auditView === "MY_ACTIVITY" ? "Your sign-ins, account operations, and changes are recorded here." : auditView === "AUDIT" ? "Review recorded activity across all staff accounts." : "Simulated SMS/email notices recorded by the banking service."}</p>
            </div>
            <div className="row-actions">
              <button className={`pill-btn ${auditView === "MY_ACTIVITY" ? "active" : ""}`} onClick={() => { navigateToTab("AUDIT", "MY_ACTIVITY"); setAuditOffset(0); run(() => loadActivityLogs("mine", "", 0)); }}>My activity</button>
              {(staff.role === "ADMIN" || staff.role === "AUDITOR") && (
                <button className={`pill-btn ${auditView === "AUDIT" ? "active" : ""}`} onClick={() => { navigateToTab("AUDIT", "AUDIT"); setAuditOffset(0); run(() => loadActivityLogs("all", "", 0)); }}>All staff</button>
              )}
              {(staff.role === "ADMIN" || staff.role === "AUDITOR") && (
                <button className={`pill-btn ${auditView === "NOTIFICATIONS" ? "active" : ""}`} onClick={() => { navigateToTab("AUDIT", "NOTIFICATIONS"); run(loadNotifications); }}>Notifications</button>
              )}
            </div>
            {auditView !== "NOTIFICATIONS" && (
            <form className="search-form" onSubmit={handleAuditFilter}>
              <input
                placeholder="Filter action (e.g. login, transfer, open)…"
                value={auditSearch}
                onChange={(event) => setAuditSearch(event.target.value)}
              />
              <button className="button-secondary" disabled={busy}>Filter</button>
            </form>
            )}
          </div>
          <div className="table-wrap">
            {auditView !== "NOTIFICATIONS" ? (
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
                    <td colSpan={5} className="empty">No activity recorded yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
            ) : (
              <table>
                <thead><tr><th>Timestamp</th><th>Channel</th><th>Recipient</th><th>Subject</th><th>Message</th><th>Status</th></tr></thead>
                <tbody>
                  {notifications.map((item) => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.channel}</td><td>{item.recipient}</td><td>{item.subject || "—"}</td><td>{item.body}</td><td><span className="status">{item.status}</span></td></tr>)}
                  {notifications.length === 0 && <tr><td colSpan={6} className="empty">No notifications recorded yet.</td></tr>}
                </tbody>
              </table>
            )}
          </div>
          {auditView !== "NOTIFICATIONS" && auditLogs.length === 100 && (
            <div className="audit-pagination">
              <button className="button-secondary" disabled={busy || auditOffset === 0} onClick={() => run(async () => {
                const nextOffset = Math.max(0, auditOffset - 100);
                setAuditOffset(nextOffset);
                await loadActivityLogs(
                  auditView === "AUDIT" ? "all" : "mine",
                  auditSearch,
                  nextOffset,
                );
              })}>Previous</button>
              <span>Showing {auditOffset + 1}–{auditOffset + auditLogs.length}</span>
              <button className="button-secondary" disabled={busy} onClick={() => run(async () => {
                const nextOffset = auditOffset + 100;
                setAuditOffset(nextOffset);
                await loadActivityLogs(
                  auditView === "AUDIT" ? "all" : "mine",
                  auditSearch,
                  nextOffset,
                );
              })}>Next</button>
            </div>
          )}
        </section>
      )}

      {activeTab === "RECONCILIATION" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Ledger reconciliation</h2>
              <p className="muted">Double-entry account and ledger balance verification.</p>
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
        </div>
      </div>

      {receipt && (
        <div className="modal-overlay receipt-overlay" onClick={() => setReceipt(null)}>
          <section className="modal-box receipt-card" role="dialog" aria-modal="true" aria-labelledby="receipt-title" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div><p className="eyebrow">SHIVA BANK · SIMULATED RECEIPT</p><h2 id="receipt-title">{receipt.type} receipt</h2></div>
              <button className="modal-close" onClick={() => setReceipt(null)} aria-label="Close receipt">✕</button>
            </div>
            <div className="receipt-amount"><span>Amount posted</span><strong>₹{receipt.amount}</strong></div>
            <dl className="receipt-details">
              <dt>Reference</dt><dd className="mono">{receipt.transaction_id}</dd>
              <dt>Date and time</dt><dd>{new Date(receipt.created_at).toLocaleString()}</dd>
              {receipt.accounts.map((accountNumber, index) => (
                <Fragment key={`${accountNumber}-${index}`}>
                  <dt>{receipt.accounts.length === 2 ? (index === 0 ? "From account" : "To account") : "Account"}</dt>
                  <dd className="mono">{accountNumber} · balance ₹{receipt.balances[index]}</dd>
                </Fragment>
              ))}
              <dt>Remark</dt><dd>{receipt.memo || "—"}</dd>
              <dt>Status</dt><dd><span className="status status-active">POSTED</span></dd>
            </dl>
            <div className="row-actions receipt-actions">
              <button className="button-secondary" onClick={() => window.print()}>Print / Save PDF</button>
              <button onClick={() => setReceipt(null)}>Done</button>
            </div>
          </section>
        </div>
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
                <a className="button-secondary button-link" href={`/api/banking/accounts/${statementAccount}/statement.csv`}>
                  Download CSV
                </a>
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
                  <option value="REVERSAL">Reversal</option>
                  <option value="INTEREST">Interest</option>
                  <option value="LOAN_DISBURSEMENT">Loan Disbursement</option>
                  <option value="LOAN_REPAYMENT">Loan Repayment</option>
                  <option value="FD_OPEN">Fixed Deposit Open</option>
                  <option value="FD_MATURITY">FD Maturity</option>
                  <option value="FD_PREMATURE_CLOSURE">FD Premature Closure</option>
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

      {sessionLoginOpen && (
        <div className="modal-overlay" onClick={() => setSessionLoginOpen(false)}>
          <div className="modal-box session-modal" role="dialog" aria-modal="true" aria-labelledby="session-login-title" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div><p className="eyebrow">INDEPENDENT STAFF SESSION</p><h2 id="session-login-title">Add staff login</h2></div>
              <button className="modal-close" onClick={() => setSessionLoginOpen(false)} aria-label="Close">✕</button>
            </div>
            <form className="stack" onSubmit={addStaffSession}>
              <label>Username<input autoComplete="username" value={sessionUsername} onChange={(event) => setSessionUsername(event.target.value)} required /></label>
              <label>Password<input type="password" autoComplete="current-password" value={sessionPassword} onChange={(event) => setSessionPassword(event.target.value)} required /></label>
              <button disabled={busy}>{busy ? "Signing in…" : "Sign in and keep current session"}</button>
            </form>
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
                  placeholder="At least 12 characters"
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

      {loanDetails && (
        <div className="modal-overlay" onClick={() => setLoanDetails(null)}>
          <div className="modal-box wide" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <div><h2>{loanDetails.loan_type} loan · {loanDetails.customer_name}</h2><p className="muted">Status: {loanDetails.status} · Outstanding ₹{loanDetails.outstanding} · EMI ₹{loanDetails.emi}</p></div>
              <button className="modal-close" onClick={() => setLoanDetails(null)}>✕</button>
            </div>
            {staff.role !== "AUDITOR" && loanDetails.status === "ACTIVE" && (
              <form className="statement-filter-form" onSubmit={submitRepayment}>
                <label>Repayment amount (₹)<input inputMode="decimal" value={repaymentAmount} onChange={(event) => setRepaymentAmount(event.target.value)} required /></label>
                <label>Remark<input value={repaymentMemo} onChange={(event) => setRepaymentMemo(event.target.value)} /></label>
                <button disabled={busy}>Post repayment</button>
              </form>
            )}
            <h3>Repayment history</h3>
            <div className="table-wrap">
              <table><thead><tr><th>Date</th><th>Amount</th><th>Principal</th><th>Interest</th></tr></thead>
                <tbody>
                  {loanDetails.repayments.map((repayment) => <tr key={repayment.id}><td>{new Date(repayment.date).toLocaleString()}</td><td>₹{repayment.amount}</td><td>₹{repayment.principal}</td><td>₹{repayment.interest}</td></tr>)}
                  {loanDetails.repayments.length === 0 && <tr><td colSpan={4} className="empty">No repayments posted.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {reverseTransaction && (
        <div className="modal-overlay" onClick={() => setReverseTransaction(null)}>
          <div className="modal-box" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head"><div><h2>Reverse transaction</h2><p className="muted">This creates a balancing ledger entry and does not delete the original transaction.</p></div><button className="modal-close" onClick={() => setReverseTransaction(null)}>✕</button></div>
            <p className="mono">{reverseTransaction.transaction_id} · {reverseTransaction.type}</p>
            <form className="stack" onSubmit={submitReversal}>
              <label>Reason (at least 5 characters)<input minLength={5} maxLength={250} value={reversalReason} onChange={(event) => setReversalReason(event.target.value)} required /></label>
              <button disabled={busy}>Post reversal</button>
            </form>
          </div>
        </div>
      )}

      {staffPasswordTarget && (
        <div className="modal-overlay" onClick={() => setStaffPasswordTarget(null)}>
          <div className="modal-box" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head"><div><h2>Reset staff password</h2><p className="muted">@{staffPasswordTarget.username} · minimum 12 characters</p></div><button className="modal-close" onClick={() => setStaffPasswordTarget(null)}>✕</button></div>
            <form className="stack" onSubmit={resetStaffPassword}>
              <label>Temporary password<input type="password" minLength={12} maxLength={256} value={staffResetPassword} onChange={(event) => setStaffResetPassword(event.target.value)} required /></label>
              <button disabled={busy}>Reset password and revoke sessions</button>
            </form>
          </div>
        </div>
      )}

      <footer>
        Secure Banking Operations · Staff actions are logged for administrative review
      </footer>
    </main>
  );
}
