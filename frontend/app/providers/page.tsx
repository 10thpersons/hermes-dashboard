'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { StatCard } from '@/components/stat-card';
import { Server, Boxes, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface Provider {
  id: string;
  provider: string;
  testStatus: string;
  backoffLevel: number;
  lastError: string | null;
  errorCode: number | null;
  baseUrl: string;
  hasApiKey: boolean;
  status: 'active' | 'backoff' | 'error' | 'unknown';
  modelCount: number;
}

interface ProvidersResponse {
  providers: Provider[];
  count: number;
  modelsAvailable: number | null;
  error?: string;
}

interface ModelItem {
  id: string;
  object: string;
  owned_by: string;
}

interface ModelsResponse {
  models: ModelItem[];
  count: number;
  error?: string;
}

const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  active: { cls: 'bg-green-500/10 text-green-400', label: 'Active' },
  backoff: { cls: 'bg-yellow-500/10 text-yellow-400', label: 'Backoff' },
  error: { cls: 'bg-red-500/10 text-red-400', label: 'Error' },
  unknown: { cls: 'bg-zinc-500/10 text-zinc-400', label: 'Unknown' },
};

function shortName(id: string, provider: string): string {
  // Truncate long openai-compatible-chat-<uuid> names to something readable.
  if (provider.startsWith('openai-compatible-chat-')) {
    return 'openai-compat-' + provider.split('-').slice(-1)[0].slice(0, 8);
  }
  return provider || id.slice(0, 16);
}

export default function ProvidersPage() {
  const {
    data: provData,
    isLoading: provLoading,
    error: provError,
  } = useQuery<ProvidersResponse>({
    queryKey: ['providers'],
    queryFn: fetchers.providers,
    refetchInterval: 30000,
  });

  const { data: modelData, isLoading: modelsLoading } =
    useQuery<ModelsResponse>({
      queryKey: ['provider-models'],
      queryFn: fetchers.providerModels,
      refetchInterval: 60000,
    });

  if (provLoading)
    return (
      <div className="text-[var(--text-secondary)]">Loading providers…</div>
    );

  const providers = provData?.providers ?? [];
  const models = modelData?.models ?? [];
  const active = providers.filter((p) => p.status === 'active').length;
  const errored = providers.filter((p) => p.status === 'error').length;
  const inBackoff = providers.filter((p) => p.status === 'backoff').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">VansRoute Providers</h1>
        {provData?.error && (
          <span className="text-xs text-red-400 bg-red-500/10 px-3 py-1 rounded-full">
            {provData.error}
          </span>
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Server}
          label="Total Providers"
          value={provData?.count ?? 0}
        />
        <StatCard
          icon={CheckCircle2}
          label="Active"
          value={active}
          sub={errored > 0 ? `${errored} erroring` : 'all healthy'}
        />
        <StatCard
          icon={AlertTriangle}
          label="In Backoff"
          value={inBackoff}
          sub={errored > 0 ? `${errored} errored` : 'none'}
        />
        <StatCard
          icon={Boxes}
          label="Models Available"
          value={modelData?.count ?? provData?.modelsAvailable ?? '—'}
        />
      </div>

      {/* Provider table */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)]">
            Provider Connections
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--text-secondary)] border-b border-[var(--border)]">
                <th className="px-5 py-2.5 font-medium">Provider</th>
                <th className="px-5 py-2.5 font-medium">Status</th>
                <th className="px-5 py-2.5 font-medium">Models</th>
                <th className="px-5 py-2.5 font-medium">Backoff</th>
                <th className="px-5 py-2.5 font-medium">Last Error</th>
                <th className="px-5 py-2.5 font-medium">Code</th>
              </tr>
            </thead>
            <tbody>
              {providers.length === 0 && !provError && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-8 text-center text-[var(--text-secondary)]"
                  >
                    No provider connections found.
                  </td>
                </tr>
              )}
              {providers.map((p) => {
                const badge = STATUS_BADGE[p.status] ?? STATUS_BADGE.unknown;
                return (
                  <tr
                    key={p.id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)]/40"
                  >
                    <td className="px-5 py-3">
                      <div className="font-mono text-xs">
                        {shortName(p.id, p.provider)}
                      </div>
                      <div className="text-[10px] text-[var(--text-secondary)] truncate max-w-[220px]">
                        {p.baseUrl || '—'}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`text-xs px-2.5 py-1 rounded-full ${badge.cls}`}
                      >
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-[var(--text-secondary)]">
                      {p.modelCount}
                    </td>
                    <td className="px-5 py-3">
                      {p.backoffLevel > 0 ? (
                        <span className="text-yellow-400 font-mono">
                          {p.backoffLevel}
                        </span>
                      ) : (
                        <span className="text-[var(--text-secondary)]">0</span>
                      )}
                    </td>
                    <td
                      className="px-5 py-3 text-xs text-[var(--text-secondary)] max-w-[260px] truncate"
                      title={p.lastError ?? ''}
                    >
                      {p.lastError ?? '—'}
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-[var(--text-secondary)]">
                      {p.errorCode ?? '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Models grid */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)]">
            Available Models
          </h2>
          <span className="text-xs text-[var(--text-secondary)]">
            {models.length} models
          </span>
        </div>
        {modelsLoading ? (
          <div className="text-[var(--text-secondary)] text-sm">
            Loading models…
          </div>
        ) : models.length === 0 ? (
          <div className="text-[var(--text-secondary)] text-sm">
            {modelData?.error ?? 'No models available.'}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {models.map((m) => (
              <div
                key={m.id}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-3 hover:border-[var(--accent)]/40 transition-colors"
              >
                <div className="font-mono text-xs break-all leading-relaxed">
                  {m.id}
                </div>
                {m.owned_by && (
                  <div className="mt-1.5 text-[10px] text-[var(--text-secondary)] uppercase tracking-wide">
                    {m.owned_by}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
