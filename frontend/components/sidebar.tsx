"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  Clock,
  Settings,
  Activity,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/sessions", label: "Sessions", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/automation", label: "Automation", icon: Clock },
  { href: "/config", label: "Config", icon: Settings },
  { href: "/system", label: "System", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-[var(--border)] bg-[var(--bg-secondary)] flex flex-col">
      <div className="p-5 border-b border-[var(--border)]">
        <span className="font-mono text-lg font-bold tracking-widest text-[var(--accent)]">
          HERMES
        </span>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
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
      <div className="p-4 text-xs text-[var(--text-secondary)] border-t border-[var(--border)]">
        v1.0.0
      </div>
    </aside>
  );
}
