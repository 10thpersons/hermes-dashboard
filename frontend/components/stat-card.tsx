import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sub?: string;
}

export function StatCard({ icon: Icon, label, value, sub }: StatCardProps) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg bg-[var(--accent)]/10">
          <Icon
            size={18}
            className="text-[var(--accent)]"
          />
        </div>
        <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      </div>
      <div className="text-2xl font-semibold">{value}</div>
      {sub && (
        <div className="text-xs text-[var(--text-secondary)] mt-1">{sub}</div>
      )}
    </div>
  );
}
