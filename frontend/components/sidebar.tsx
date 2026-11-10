'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  Clock,
  Settings,
  Activity,
  Server,
  BarChart3,
  Menu,
  X,
  Sun,
  Moon,
  Megaphone,
} from 'lucide-react';

const NAV = [
  { href: '/', label: 'Overview', icon: LayoutDashboard },
  { href: '/sessions', label: 'Sessions', icon: MessageSquare },
  { href: '/affiliate', label: 'Affiliate', icon: Megaphone },
  { href: '/knowledge', label: 'Knowledge', icon: BookOpen },
  { href: '/automation', label: 'Automation', icon: Clock },
  { href: '/providers', label: 'Providers', icon: Server },
  { href: '/usage', label: 'Usage', icon: BarChart3 },
  { href: '/config', label: 'Config', icon: Settings },
  { href: '/system', label: 'System', icon: Activity },
];

/** Theme toggle: reads/writes localStorage + data-theme on <html> */
function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  // Sync from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('hermes-theme') as
      'dark' | 'light' | null;
    if (stored) {
      setTheme(stored);
      document.documentElement.setAttribute('data-theme', stored);
    }
  }, []);

  const toggle = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('hermes-theme', next);
    document.documentElement.setAttribute('data-theme', next);
  }, [theme]);

  return (
    <button
      onClick={toggle}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const navLinks = (
    <nav
      className="flex-1 overflow-y-auto p-3 space-y-0.5"
      aria-label="Main"
    >
      {NAV.map(({ href, label, icon: Icon }) => {
        const active =
          pathname === href || (href !== '/' && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setOpen(false)}
            aria-current={active ? 'page' : undefined}
            className={`flex h-9 items-center gap-2.5 px-3 rounded-lg text-sm transition-colors ${
              active
                ? 'bg-[var(--bg-tertiary)] text-[var(--text-primary)] ring-1 ring-inset ring-[var(--border)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <Icon
              size={16}
              strokeWidth={1.5}
              className="shrink-0"
            />
            {label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden flex h-14 shrink-0 items-center justify-between px-4 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <span className="text-base font-medium tracking-tight text-[var(--text-primary)]">
          Hermes
        </span>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex bg-black/50">
          <div className="w-60 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col">
            <div className="h-14 px-5 border-b border-[var(--border)] flex items-center justify-between">
              <span className="text-base font-medium tracking-tight text-[var(--text-primary)]">
                Hermes
              </span>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="text-[var(--text-secondary)]"
              >
                <X size={18} />
              </button>
            </div>
            {navLinks}
            <div className="p-3 border-t border-[var(--border)]">
              <ThemeToggle />
            </div>
            <div className="px-5 py-3 text-xs text-[var(--text-muted)] border-t border-[var(--border)]">
              v1.0.0
            </div>
          </div>
          <div
            className="flex-1"
            onClick={() => setOpen(false)}
          />
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-60 shrink-0 border-r border-[var(--border)] bg-[var(--bg-secondary)] flex-col">
        <div className="h-14 px-5 flex items-center border-b border-[var(--border)]">
          <span className="text-base font-medium tracking-tight text-[var(--text-primary)]">
            Hermes
          </span>
        </div>
        {navLinks}
        <div className="p-3 border-t border-[var(--border)] flex items-center justify-between">
          <ThemeToggle />
          <span className="text-xs text-[var(--text-muted)]">v1.0.0</span>
        </div>
      </aside>
    </>
  );
}
