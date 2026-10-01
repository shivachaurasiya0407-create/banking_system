"use client"

import { useState } from "react"
import { ArrowDownLeft, ArrowUpRight, Bell, ChevronDown, CreditCard, LayoutDashboard, Menu, MoreHorizontal, Plus, Search, Send, Settings, ShieldCheck, Sparkles, Wallet, X } from "lucide-react"

const accounts = [
  { name: "Everyday account", number: "•••• 7524", balance: "₹2,30,000", tone: "ivory", kind: "Savings" },
  { name: "Reserve account", number: "•••• 0065", balance: "₹89,000", tone: "ink-card", kind: "Current" },
]
const transactions = [
  { title: "Salary credit", meta: "Today, 09:42 AM", amount: "+ ₹85,000", type: "credit", icon: ArrowDownLeft },
  { title: "Zomato", meta: "Yesterday, 08:16 PM", amount: "− ₹640", type: "debit", icon: ArrowUpRight },
  { title: "Electricity bill", meta: "18 Sep 2026, 11:30 AM", amount: "− ₹2,450", type: "debit", icon: ArrowUpRight },
  { title: "Transfer from Rishi", meta: "16 Sep 2026, 04:20 PM", amount: "+ ₹12,000", type: "credit", icon: ArrowDownLeft },
]

export default function Home() {
  const [active, setActive] = useState("Overview")
  const [menuOpen, setMenuOpen] = useState(false)
  const nav = ["Overview", "Accounts", "Transfers", "Transactions"]
  return (
    <main className="app-shell">
      <aside className={menuOpen ? "sidebar open" : "sidebar"}>
        <div className="brand"><div className="brand-mark"><Sparkles /></div><span>northstar</span></div>
        <button className="close-menu" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X /></button>
        <div className="profile-mini"><div className="avatar">SH</div><div><strong>Shiva</strong><span>Personal banking</span></div><ChevronDown className="chevron" /></div>
        <p className="nav-label">Workspace</p>
        <nav aria-label="Main navigation">{nav.map((item) => <button key={item} className={active === item ? "nav-item active" : "nav-item"} onClick={() => { setActive(item); setMenuOpen(false) }}>{item === "Overview" ? <LayoutDashboard /> : item === "Accounts" ? <Wallet /> : item === "Transfers" ? <Send /> : <CreditCard />}<span>{item}</span>{item === "Transactions" && <em>4</em>}</button>)}</nav>
        <div className="sidebar-bottom"><p className="nav-label">Support</p><button className="nav-item"><Settings /><span>Settings</span></button><button className="nav-item"><ShieldCheck /><span>Security</span></button><div className="help-card"><span>Need a hand?</span><strong>Visit help center</strong><ArrowUpRight /></div></div>
      </aside>
      <section className="content">
        <header className="topbar"><button className="menu-button" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu /></button><div className="breadcrumb">Personal <span>/</span> {active}</div><div className="top-actions"><button className="icon-button" aria-label="Search"><Search /></button><button className="icon-button notification" aria-label="Notifications"><Bell /><i /></button><div className="top-avatar">SH</div></div></header>
        <div className="page-wrap"><div className="welcome"><div><p className="eyebrow">MONDAY, SEPTEMBER 29, 2026</p><h1>Good morning, Shiva <span>✦</span></h1><p className="subheading">A clear view of your financial world.</p></div><button className="primary-button"><Plus /> New payment</button></div>
          <section className="stats-grid"><div className="balance-card"><div className="card-top"><span>Total balance <small>INR</small></span><button aria-label="More balance options">•••</button></div><div className="balance">₹3,19,000<span>.00</span></div><div className="balance-meta"><span className="positive">↗ 8.4%</span><span>vs. last month</span></div><div className="sparkline"><svg viewBox="0 0 460 64" preserveAspectRatio="none" aria-hidden="true"><path d="M0 53 C35 52, 40 44, 72 47 S112 32, 145 39 S180 22, 210 30 S248 18, 275 24 S304 10, 334 20 S372 12, 400 17 S437 5, 460 8" fill="none" stroke="currentColor" strokeWidth="3" /></svg></div></div><div className="stat-card"><div className="stat-icon green"><ArrowDownLeft /></div><div><span>Money in</span><strong>₹97,000</strong><small className="positive">+ 12.6% this month</small></div></div><div className="stat-card"><div className="stat-icon orange"><ArrowUpRight /></div><div><span>Money out</span><strong>₹24,680</strong><small>− 4.2% this month</small></div></div></section>
          <div className="section-grid"><section><div className="section-heading"><div><h2>Your accounts</h2><p>Manage your money in one place.</p></div><button className="text-button">View all <ArrowUpRight /></button></div><div className="accounts-grid">{accounts.map((account) => <article className={`account-card ${account.tone}`} key={account.name}><div className="account-head"><span>{account.kind}</span><MoreHorizontal /></div><div className="account-name">{account.name}</div><div className="account-number">{account.number}</div><div className="account-footer"><strong>{account.balance}</strong><span>Available balance</span></div></article>)}<button className="add-account"><span><Plus /></span><strong>Add account</strong><small>Connect another account</small></button></div></section>
            <section className="transactions"><div className="section-heading"><div><h2>Recent activity</h2><p>Your latest account movements.</p></div><button className="text-button">See all <ArrowUpRight /></button></div><div className="transaction-list">{transactions.map((transaction) => { const Icon = transaction.icon; return <div className="transaction" key={transaction.title}><div className={`transaction-icon ${transaction.type}`}><Icon /></div><div className="transaction-info"><strong>{transaction.title}</strong><span>{transaction.meta}</span></div><b className={transaction.type}>{transaction.amount}</b></div> })}</div></section></div>
          <section className="insight"><div className="insight-icon"><Sparkles /></div><div><span>YOUR MONTHLY INSIGHT</span><h3>You&apos;re spending 18% less than last month.</h3><p>That&apos;s ₹5,420 more kept in your pocket. Keep it up.</p></div><button className="secondary-button">View insights <ArrowUpRight /></button></section>
        </div>
      </section>
    </main>
  )
}
