'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { StatCard } from '@/components/stat-card';
import { BarChart3, Hash, Layers, Coins } from 'lucide-react';

function formatTokens(n: number): string {
  if (!n) return '0';
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + 'B';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function UsagePage() {
  const { data: summary } = useQuery({
    queryKey: ['usage-summary'],
    queryFn: fetchers.usageSummary,
  });
  const { data: daily } = useQuery({
    queryKey: ['usage-daily'],
    queryFn: () => fetchers.usageDaily(30),
  });
  const { data: byModel } = useQuery({
    queryKey: ['usage-by-model'],
    queryFn: fetchers.usageByModel,
  });

  const maxDaily = daily?.length
    ? Math.max(...daily.map((d: any) => d.total_tokens)) || 1
    : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Token Usage</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Coins}
          label="Total Tokens"
          value={formatTokens(summary?.total_tokens ?? 0)}
          sub="input + output + cache + reasoning"
        />
        <StatCard
          icon={Layers}
          label="Total Sessions"
          value={summary?.total_sessions ?? '—'}
        />
        <StatCard
          icon={Hash}
          label="Avg / Session"
          value={formatTokens(summary?.avg_tokens_per_session ?? 0)}
        />
        <StatCard
          icon={BarChart3}
          label="Models"
          value={summary?.by_model?.length ?? '—'}
        />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
          Daily Usage (Last 30 Days)
        </h2>
        {daily?.length ? (
          <div className="flex items-end gap-1 h-48 overflow-x-auto">
            {daily.map((d: any) => (
              <div
                key={d.date}
                className="flex-1 min-w-[8px] flex flex-col items-center justify-end h-full group relative"
              >
                <div
                  className="w-full rounded-t bg-[var(--accent)] transition-opacity hover:opacity-80"
                  style={{
                    height: `${(d.total_tokens / maxDaily) * 100}%`,
                    minHeight: d.total_tokens > 0 ? '2px' : '0',
                  }}
                />
                <div className="absolute -top-8 hidden group-hover:block bg-[var(--bg-tertiary)] border border-[var(--border)] rounded px-2 py-1 text-xs whitespace-nowrap z-10">
                  {formatDate(d.date)}: {formatTokens(d.total_tokens)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-[var(--text-secondary)]">No data</div>
        )}
        {daily?.length ? (
          <div className="flex justify-between mt-2 text-xs text-[var(--text-secondary)]">
            <span>{formatDate(daily[0].date)}</span>
            <span>{formatDate(daily[daily.length - 1].date)}</span>
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
          Usage by Model
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-secondary)] border-b border-[var(--border)]">
                <th className="py-2 pr-4 font-medium">Model</th>
                <th className="py-2 px-4 font-medium text-right">Sessions</th>
                <th className="py-2 px-4 font-medium text-right">
                  Total Tokens
                </th>
                <th className="py-2 px-4 font-medium text-right">Input</th>
                <th className="py-2 px-4 font-medium text-right">Output</th>
                <th className="py-2 pl-4 font-medium text-right">
                  Avg / Session
                </th>
              </tr>
            </thead>
            <tbody>
              {(byModel ?? []).map((m: any) => (
                <tr
                  key={m.model}
                  className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors"
                >
                  <td className="py-2 pr-4 font-mono">{m.model}</td>
                  <td className="py-2 px-4 text-right">{m.sessions}</td>
                  <td className="py-2 px-4 text-right font-semibold">
                    {formatTokens(m.total_tokens)}
                  </td>
                  <td className="py-2 px-4 text-right text-[var(--text-secondary)]">
                    {formatTokens(m.input_tokens)}
                  </td>
                  <td className="py-2 px-4 text-right text-[var(--text-secondary)]">
                    {formatTokens(m.output_tokens)}
                  </td>
                  <td className="py-2 pl-4 text-right text-[var(--text-secondary)]">
                    {formatTokens(m.avg_tokens_per_session)}
                  </td>
                </tr>
              ))}
              {!byModel?.length ? (
                <tr>
                  <td
                    colSpan={6}
                    className="py-4 text-center text-[var(--text-secondary)]"
                  >
                    No data
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
