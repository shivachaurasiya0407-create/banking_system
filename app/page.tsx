"use client"

import { useMemo, useState } from "react"
import { Activity, ArrowDownLeft, ArrowUpRight, BarChart3, Bell, ChevronDown, CircleDollarSign, CreditCard, FilePlus2, LayoutDashboard, Menu, MoreHorizontal, Plus, Search, Settings, ShieldCheck, UserRound, Users, WalletCards, X } from "lucide-react"

type Account = { name: string; initials: string; account: string; type: string; balance: string; status: "Active" | "Pending" | "Frozen" }

const accounts: Account[] = [
  { name: "Aditya Raj", initials: "AR", account: "•••• 5538", type: "Savings Account", balance: "₹90,000.00", status: "Active" },
  { name: "Shiv Chaurasiya", initials: "SC", account: "•••• 8051", type: "Current Account", balance: "₹12,000.00", status: "Frozen" },
  { name: "Meera Nair", initials: "MN", account: "•••• 2194", type: "Savings Account", balance: "₹1,24,500.00", status: "Active" },
  { name: "Rohan Mehta", initials: "RM", account: "•••• 7741", type: "Business Account", balance: "₹4,50,000.00", status: "Pending" },
]

const transactions = [
  { label: "Salary credit · Aditya Raj", meta: "Today, 10:42 AM", amount: "+ ₹45,000", kind: "credit" },
  { label: "NEFT transfer · Shiv Chaurasiya", meta: "Today, 09:18 AM", amount: "− ₹8,500", kind: "debit" },
  { label: "Cash deposit · Meera Nair", meta: "Yesterday, 04:32 PM", amount: "+ ₹22,000", kind: "credit" },
  { label: "UPI payment · Rohan Mehta", meta: "Yesterday, 02:15 PM", amount: "− ₹3,240", kind: "debit" },
]

export default function Home() {
  const [activeNav, setActiveNav] = useState("Overview")
  const [query, setQuery] = useState("")
  const [showNotice, setShowNotice] = useState(true)
  const [showMobileNav, setShowMobileNav] = useState(false)
  const [showNewAccount, setShowNewAccount] = useState(false)
  const [toast, setToast] = useState("")
  const [accountRows, setAccountRows] = useState(accounts)
  const filteredAccounts = useMemo(() => accountRows.filter((account) => `${account.name} ${account.account} ${account.type}`.toLowerCase().includes(query.toLowerCase())), [accountRows, query])

  const action = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 2600) }

  return <div className="shell">
    <aside className={`sidebar ${showMobileNav ? "mobile-open" : ""}`}>
      <div className="brand"><div className="brand-mark">S</div><div><div className="brand-name">Shiv Bank</div><div className="brand-sub">Operations console</div></div><button className="icon-btn mobile-close" onClick={() => setShowMobileNav(false)} aria-label="Close menu"><X /></button></div>
      <div className="nav-label">Workspace</div>
      <nav className="nav" aria-label="Primary navigation">
        {[{label:"Overview",icon:LayoutDashboard},{label:"Accounts",icon:Users},{label:"Transactions",icon:ArrowUpRight},{label:"Approvals",icon:ShieldCheck}].map(({label,icon:Icon}) => <button key={label} className={`nav-item ${activeNav === label ? "active" : ""}`} onClick={() => { setActiveNav(label); setShowMobileNav(false) }}><Icon className="nav-icon" /><span>{label}</span></button>)}
      </nav>
      <div className="nav-label">Tools</div>
      <nav className="nav"><button className="nav-item" onClick={() => action("Reports are being prepared") }><BarChart3 className="nav-icon" /><span>Reports</span></button><button className="nav-item" onClick={() => action("Settings opened") }><Settings className="nav-icon" /><span>Settings</span></button></nav>
      <div className="sidebar-bottom"><div className="profile"><div className="avatar">AK</div><div className="profile-copy"><div className="profile-name">Aarav Kulkarni</div><div className="profile-role">Branch Manager · BRC-014</div></div><ChevronDown className="profile-copy" size={15} /></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb"><button className="icon-btn mobile-menu" onClick={() => setShowMobileNav(true)} aria-label="Open menu"><Menu /></button><span>Branch 014 / </span><strong>{activeNav}</strong></div><div className="top-actions"><label className="search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search accounts..." aria-label="Search accounts" /></label><button className="icon-btn" onClick={() => action("You are all caught up")} aria-label="Notifications"><Bell size={16} /></button></div></header>
      <div className="content">
        <section className="page-heading"><div><p className="eyebrow">Wednesday, 08 October 2026</p><h1 className="page-title">Good morning, Aarav</h1><p className="page-description">Here&apos;s your branch activity and daily operations at a glance.</p></div><button className="primary-btn" onClick={() => { setActiveNav("Accounts"); setShowNewAccount(true) }}><Plus size={16} /> Open new account</button></section>
        <section className="metric-grid" aria-label="Branch summary"><Metric icon={WalletCards} label="Total deposits" value="₹8.42 Cr" note="12.4% from last month" /><Metric icon={Users} label="Active customers" value="2,846" note="48 added this month" /><Metric icon={Activity} label="Transactions today" value="184" note="₹12.8L processed" /><Metric icon={ShieldCheck} label="Pending approvals" value="07" note="Requires your review" /></section>
        {activeNav === "Accounts" ? <AccountsWorkspace accounts={filteredAccounts} showNewAccount={showNewAccount} setShowNewAccount={setShowNewAccount} onAction={action} onCreate={(account) => { setAccountRows((rows) => [account, ...rows]); setShowNewAccount(false); action("Account created and queued for KYC review") }} /> : <div className="dashboard-grid"><div className="panel"><div className="panel-heading"><div><h2 className="panel-title">Recent accounts</h2><p className="panel-subtitle">Customer accounts requiring attention or recently updated</p></div><button className="link-btn" onClick={() => setActiveNav("Accounts")}>View all accounts</button></div><div className="table-wrap"><table className="table"><thead><tr><th>Customer</th><th>Account</th><th>Balance</th><th>Status</th><th></th></tr></thead><tbody>{filteredAccounts.map((account) => <tr key={account.account}><td><div className="customer"><div className="customer-avatar">{account.initials}</div><div><div className="customer-name">{account.name}</div><div className="customer-meta">{account.type}</div></div></div></td><td>{account.account}</td><td>{account.balance}</td><td><span className={`badge ${account.status.toLowerCase()}`}>{account.status}</span></td><td><button className="icon-btn" onClick={() => action(`${account.name}'s account selected`)} aria-label={`More options for ${account.name}`}><MoreHorizontal size={15} /></button></td></tr>)}</tbody></table></div></div><div className="panel"><div className="panel-heading"><div><h2 className="panel-title">Activity feed</h2><p className="panel-subtitle">Your team&apos;s latest actions</p></div><button className="icon-btn" onClick={() => action("Activity refreshed")} aria-label="Refresh activity"><Activity size={15} /></button></div><div className="activity-list"><ActivityItem text={<>You approved a <strong>₹45,000</strong> NEFT transfer</>} time="12 minutes ago" /><ActivityItem text={<>Priya added a new customer, <strong>Meera Nair</strong></>} time="46 minutes ago" /><ActivityItem text={<>Account <strong>•••• 8051</strong> was temporarily frozen</>} time="1 hour ago" /><ActivityItem text={<>Daily settlement report is ready to view</>} time="2 hours ago" /></div><div className="quick-actions"><button className="quick-action" onClick={() => action("Deposit workflow started")}><ArrowDownLeft size={15} /> Record deposit</button><button className="quick-action" onClick={() => action("Transfer workflow started")}><ArrowUpRight size={15} /> Make transfer</button><button className="quick-action" onClick={() => action("Customer lookup opened")}><UserRound size={15} /> Find customer</button><button className="quick-action" onClick={() => action("Report export started")}><FilePlus2 size={15} /> Export report</button></div></div></div>
        }
        {showNotice && <div className="notice"><CircleDollarSign size={18} /><div className="notice-text"><strong>Daily cash position reminder</strong>Reconcile your branch cash drawer before 5:00 PM. The latest balance is ₹6,48,200. <button className="link-btn" onClick={() => setShowNotice(false)}>Dismiss</button></div></div>}
      </div>
    </main>{toast && <div role="status" style={{position:"fixed",right:24,bottom:24,background:"#102b46",color:"white",padding:"13px 17px",borderRadius:8,fontSize:12,boxShadow:"0 8px 24px #102b4633"}}>{toast}</div>}
  </div>
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof WalletCards; label: string; value: string; note: string }) { return <article className="metric-card"><div className="metric-top"><span>{label}</span><div className="metric-icon"><Icon size={16} /></div></div><div className="metric-value">{value}</div><div className="metric-note"><span className="positive">↗ </span>{note}</div></article> }
function ActivityItem({ text, time }: { text: React.ReactNode; time: string }) { return <div className="activity"><div className="activity-dot" /><div className="activity-copy"><div>{text}</div><div className="activity-time">{time}</div></div></div> }

function AccountsWorkspace({ accounts, showNewAccount, setShowNewAccount, onAction, onCreate }: { accounts: Account[]; showNewAccount: boolean; setShowNewAccount: (value: boolean) => void; onAction: (message: string) => void; onCreate: (account: Account) => void }) {
  const [name, setName] = useState("")
  const [type, setType] = useState("Savings Account")
  const submit = () => { if (!name.trim()) return onAction("Enter a customer name first"); onCreate({ name: name.trim(), initials: name.trim().split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase(), account: "•••• " + Math.floor(1000 + Math.random() * 8999), type, balance: "₹0.00", status: "Pending" }); setName("") }
  return <section className="accounts-workspace"><div className="accounts-toolbar"><div><p className="eyebrow">Customer servicing</p><h2 className="workspace-title">Accounts management</h2><p className="panel-subtitle">Search, review and onboard customer accounts for Branch 014.</p></div><button className="primary-btn" onClick={() => setShowNewAccount(!showNewAccount)}><Plus size={16} /> New account</button></div>{showNewAccount && <div className="new-account-card"><div><strong>Open a customer account</strong><span>Capture the basic details to send this account for KYC review.</span></div><input className="account-input" value={name} onChange={(event) => setName(event.target.value)} placeholder="Customer full name" aria-label="Customer full name" /><select className="account-input" value={type} onChange={(event) => setType(event.target.value)} aria-label="Account type"><option>Savings Account</option><option>Current Account</option><option>Business Account</option></select><button className="primary-btn" onClick={submit}>Create account</button></div>}<div className="panel accounts-panel"><div className="panel-heading"><div><h2 className="panel-title">All customer accounts</h2><p className="panel-subtitle">{accounts.length} records matching your search</p></div><button className="link-btn" onClick={() => onAction("Account export queued")}>Export CSV</button></div><div className="table-wrap"><table className="table"><thead><tr><th>Customer</th><th>Account number</th><th>Balance</th><th>Status</th><th>Action</th></tr></thead><tbody>{accounts.map((account) => <tr key={account.account}><td><div className="customer"><div className="customer-avatar">{account.initials}</div><div><div className="customer-name">{account.name}</div><div className="customer-meta">{account.type}</div></div></div></td><td>{account.account}</td><td>{account.balance}</td><td><span className={`badge ${account.status.toLowerCase()}`}>{account.status}</span></td><td><button className="link-btn" onClick={() => onAction(`${account.name}'s profile opened`)}>Review</button></td></tr>)}</tbody></table></div></div></section>
}
