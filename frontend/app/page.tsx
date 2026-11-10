'use client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { StatCard } from '@/components/stat-card';
import { SkeletonCard } from '@/components/skeleton';
import {
  MessageSquare,
  Clock,
  RefreshCw,
  BarChart3,
  Server,
} from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect } from 'react';

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const {
    data: health,
    isLoading: healthLoading,
    dataUpdatedAt: healthUpdated,
  } = useQuery({
    queryKey: ['health'],
    queryFn: fetchers.systemHealth,
    refetchInterval: 30000,
  });
  const {
    data: sessions,
    isLoading: sessionsLoading,
    dataUpdatedAt: sessionsUpdated,
  } = useQuery({
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

  async function refreshAll() {
    setRefreshing(true);
    try {
      await Promise.all(
        [['health'], ['sessions'], ['cron'], ['usage']].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      setLastUpdated(new Date());
    } finally {
      setRefreshing(false);
    }
  }

  const cpuHigh = Number(health?.cpu_percent) >= 90;
  const diskHigh = parseInt(String(disk?.percent), 10) >= 85;

  function formatTime(d: Date): string {
    return d.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-medium tracking-tight">Overview</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-muted)] tabular-nums">
            Updated {formatTime(lastUpdated)}
          </span>
          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-60 transition-colors"
            title="Refresh all"
            aria-label="Refresh all"
          >
            <RefreshCw
              size={16}
              strokeWidth={1.5}
              className={refreshing ? 'animate-spin' : ''}
            />
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
        {healthLoading ? (
          <SkeletonCard />
        ) : (
          <StatCard
            label="Uptime"
            value={health?.uptime || '—'}
            sub={health?.hostname}
          />
        )}
        {healthLoading ? (
          <SkeletonCard />
        ) : (
          <StatCard
            label="Disk"
            value={disk?.percent || '—'}
            sub={disk ? `${disk.used} / ${disk.total}` : undefined}
            tone={diskHigh ? 'warn' : undefined}
          />
        )}
        {sessionsLoading ? (
          <SkeletonCard />
        ) : (
          <StatCard
            label="Sessions"
            value={sessions?.total ?? '—'}
          />
        )}
        {cronLoading ? (
          <SkeletonCard />
        ) : (
          <StatCard
            label="Cron jobs"
            value={Array.isArray(cron) ? cron.length : '—'}
          />
        )}
        {usageLoading ? (
          <SkeletonCard />
        ) : (
          <StatCard
            label="Total tokens"
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
        )}
        {healthLoading ? (
          <SkeletonCard />
        ) : (
          <StatCard
            label="CPU"
            value={health?.cpu_percent != null ? `${health.cpu_percent}%` : '—'}
            sub={
              health?.load_average
                ? `Load ${health.load_average.load1} / ${health.load_average.load5} / ${health.load_average.load15}`
                : undefined
            }
            tone={cpuHigh ? 'warn' : undefined}
          />
        )}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <Link
          href="/sessions"
          className="flex h-9 items-center gap-2 px-3 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <MessageSquare
            size={16}
            strokeWidth={1.5}
          />
          Sessions
        </Link>
        <Link
          href="/usage"
          className="flex h-9 items-center gap-2 px-3 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <BarChart3
            size={16}
            strokeWidth={1.5}
          />
          Usage
        </Link>
        <Link
          href="/automation"
          className="flex h-9 items-center gap-2 px-3 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <Clock
            size={16}
            strokeWidth={1.5}
          />
          Cron
        </Link>
        <Link
          href="/providers"
          className="flex h-9 items-center gap-2 px-3 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <Server
            size={16}
            strokeWidth={1.5}
          />
          Providers
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4 md:p-5">
          <h2 className="text-sm font-medium text-[var(--text-secondary)] mb-3">
            Services
          </h2>
          <div>
            {Object.entries(services).map(([name, status]) => (
              <div
                key={name}
                className="flex h-8 items-center justify-between"
              >
                <span className="text-sm">{name}</span>
                <span className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      status === 'active'
                        ? 'bg-[var(--success)]'
                        : 'bg-[var(--error)]'
                    }`}
                  />
                  {String(status)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4 md:p-5">
          <h2 className="text-sm font-medium text-[var(--text-secondary)] mb-3">
            Recent Sessions
          </h2>
          <div>
            {sessions?.sessions?.map((s: any) => (
              <Link
                key={s.id}
                href={`/sessions/${s.id}`}
                className="flex h-9 items-center justify-between gap-3 border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors rounded px-2"
              >
                <span className="text-sm font-mono truncate min-w-0">
                  {s.id}
                </span>
                <span className="text-xs text-[var(--text-muted)] shrink-0">
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
