import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  /** Kept for call-site compatibility; stat cards are numbers, not icons. */
  icon?: LucideIcon;
  label: string;
  value: string | number;
  sub?: string;
  /** Marks a figure that needs attention. */
  tone?: 'warn';
}

export function StatCard({ label, value, sub, tone }: StatCardProps) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4 md:p-5 min-w-0">
      <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
        {tone === 'warn' && (
          <span
            className="h-1.5 w-1.5 rounded-full bg-[var(--warning)]"
            aria-label="High"
          />
        )}
        <span className="truncate">{label}</span>
      </div>
      <div className="mt-2 text-xl md:text-2xl font-medium tabular-nums tracking-tight whitespace-nowrap">
        {value}
      </div>
      {sub && (
        <div className="mt-1 text-xs text-[var(--text-muted)] tabular-nums truncate">
          {sub}
        </div>
      )}
    </div>
  );
}
