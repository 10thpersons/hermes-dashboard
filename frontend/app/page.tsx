'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { StatCard } from '@/components/stat-card';
import { SkeletonCard } from '@/components/skeleton';
import {
  Activity,
  MessageSquare,
  Clock,
  HardDrive,
  Coins,
  Cpu,
  RefreshCw,
  BarChart3,
  Server,
} from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect } from 'react';

export default function OverviewPage() {
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const { data: health, isLoading: healthLoading, dataUpdatedAt: healthUpdated } = useQuery({
    queryKey: ['health'],
    queryFn: fetchers.systemHealth,
    refetchInterval: 30000,
  });
  const { data: sessions, isLoading: sessionsLoading, dataUpdatedAt: sessionsUpdated } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => fetchers.sessions(5),
    refetchInterval: 30000,
  });
  const { data: cron, isLoading: cronLoading } = useQuery({
    queryKey: ['cron'],
    queryFn: fetchers.cronJobs,
    refetchInterval: 30000,
  });
  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ['usage'],
    queryFn: fetchers.usageSummary,
    refetchInterval: 30000,
  });

  // Track last update time
  useEffect(() => {
    if (healthUpdated) setLastUpdated(new Date(healthUpdated));
  }, [healthUpdated, sessionsUpdated]);

  const disk = health?.disk;
  const services = health?.services || {};
  const isLoading = healthLoading || sessionsLoading;

  function formatTime(d: Date): string {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Overview</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--text-secondary)]">
            Updated {formatTime(lastUpdated)}
          </span>
          <button
            onClick={() => setLastUpdated(new Date())}
            className="p-1.5 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            title="Refresh all"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <StatCard
              icon={Activity}
              label="Uptime"
              value={health?.uptime || '—'}
              sub={health?.hostname}
            />
            <StatCard
              icon={HardDrive}
              label="Disk"
              value={disk?.percent || '—'}
              sub={disk ? `${disk.used} / ${disk.total}` : undefined}
            />
            <StatCard
              icon={MessageSquare}
              label="Sessions"
              value={sessions?.total ?? '—'}
            />
            <StatCard
              icon={Clock}
              label="Cron Jobs"
              value={Array.isArray(cron) ? cron.length : '—'}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {usageLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <StatCard
              icon={Coins}
              label="Total Tokens"
              value={
                usage?.total_tokens != null
                  ? Number(usage.total_tokens).toLocaleString()
                  : '—'
              }
              sub={
                usage?.total_sessions
                  ? `${usage.total_sessions} sessions`
                  : undefined
              }
            />
            <StatCard
              icon={Cpu}
              label="CPU"
              value={health?.cpu_percent != null ? `${health.cpu_percent}%` : '—'}
              sub={
                health?.load_average
                  ? `Load: ${health.load_average.load1} / ${health.load_average.load5} / ${health.load_average.load15}`
                  : undefined
              }
            />
          </>
        )}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <Link
          href="/sessions"
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm hover:bg-[var(--bg-tertiary)] hover:border-[var(--accent)]/30 transition-colors"
        >
          <MessageSquare size={16} />
          View Sessions
        </Link>
        <Link
          href="/usage"
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm hover:bg-[var(--bg-tertiary)] hover:border-[var(--accent)]/30 transition-colors"
        >
          <BarChart3 size={16} />
          View Usage
        </Link>
        <Link
          href="/automation"
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm hover:bg-[var(--bg-tertiary)] hover:border-[var(--accent)]/30 transition-colors"
        >
          <Clock size={16} />
          View Cron
        </Link>
        <Link
          href="/providers"
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm hover:bg-[var(--bg-tertiary)] hover:border-[var(--accent)]/30 transition-colors"
        >
          <Server size={16} />
          View Providers
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
            Services
          </h2>
          <div className="space-y-3">
            {Object.entries(services).map(([name, status]) => (
              <div
                key={name}
                className="flex items-center justify-between"
              >
                <span className="text-sm">{name}</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    status === 'active'
                      ? 'bg-green-500/10 text-green-400'
                      : 'bg-red-500/10 text-red-400'
                  }`}
                >
                  {String(status)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
            Recent Sessions
          </h2>
          <div className="space-y-2">
            {sessions?.sessions?.map((s: any) => (
              <Link
                key={s.id}
                href={`/sessions/${s.id}`}
                className="flex items-center justify-between py-1.5 border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors rounded px-1"
              >
                <span className="text-sm font-mono truncate max-w-[200px]">
                  {s.id}
                </span>
                <span className="text-xs text-[var(--text-secondary)]">
                  {s.source}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
