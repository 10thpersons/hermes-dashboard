"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  Clock,
  Settings,
  Activity,
  BarChart3,
  Menu,
  X,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/sessions", label: "Sessions", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/automation", label: "Automation", icon: Clock },
  { href: "/usage", label: "Usage", icon: BarChart3 },
  { href: "/config", label: "Config", icon: Settings },
  { href: "/system", label: "System", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const navLinks = (
    <nav className="flex-1 p-3 space-y-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setOpen(false)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              active
                ? "bg-[var(--accent)]/10 text-[var(--accent)]"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon size={18} />
            {label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">HERMES</span>
        <button onClick={() => setOpen((o) => !o)} className="text-[var(--text-secondary)]">
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-56 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col">
            <div className="p-5 border-b border-[var(--border)] flex items-center justify-between">
              <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">HERMES</span>
              <button onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            {navLinks}
            <div className="p-4 text-xs text-[var(--text-secondary)] border-t border-[var(--border)]">v1.0.0</div>
          </div>
          <div className="flex-1" onClick={() => setOpen(false)} />
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-56 shrink-0 border-r border-[var(--border)] bg-[var(--bg-secondary)] flex-col">
        <div className="p-5 border-b border-[var(--border)]">
          <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">HERMES</span>
        </div>
        {navLinks}
        <div className="p-4 text-xs text-[var(--text-secondary)] border-t border-[var(--border)]">v1.0.0</div>
      </aside>
    </>
  );
}
