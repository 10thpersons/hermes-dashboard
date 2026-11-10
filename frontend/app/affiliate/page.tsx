'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { StatCard } from '@/components/stat-card';
import {
  Megaphone,
  ShoppingBag,
  FileText,
  Coins,
  Radio,
  BookOpen,
  RefreshCw,
  Play,
  X,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import { useState } from 'react';

function ScoreBadge({ score, flags }: { score: number; flags?: string[] }) {
  const bad = (flags ?? []).length > 0;
  const tone = bad
    ? 'bg-red-500/10 text-red-400 border-red-500/30'
    : score >= 88
      ? 'bg-green-500/10 text-green-400 border-green-500/30'
      : 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border text-xs font-mono ${tone}`}
    >
      {bad ? <AlertTriangle size={11} /> : <CheckCircle2 size={11} />}
      {score.toFixed(0)}
    </span>
  );
}

export default function AffiliatePage() {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const health = useQuery({
    queryKey: ['aff-health'],
    queryFn: fetchers.affiliateHealth,
    refetchInterval: 30000,
  });

  const topics = useQuery({
    queryKey: ['aff-topics'],
    queryFn: () => fetchers.affiliateTopics(25),
    refetchInterval: 120000,
  });

  const candidates = useQuery({
    queryKey: ['aff-candidates'],
    queryFn: () => fetchers.affiliateCandidates(10),
    refetchInterval: 0,
    enabled: false,
  });

  const drafts = useQuery({
    queryKey: ['aff-drafts'],
    queryFn: fetchers.affiliateDrafts,
    refetchInterval: 30000,
  });

  const report = useQuery({
    queryKey: ['aff-report'],
    queryFn: fetchers.affiliateReport,
    refetchInterval: 60000,
  });

  const research = useQuery({
    queryKey: ['aff-research'],
    queryFn: fetchers.affiliateResearch,
    refetchInterval: 0,
  });

  const governor = useQuery({
    queryKey: ['aff-governor'],
    queryFn: fetchers.affiliateGovernor,
    refetchInterval: 30000,
  });

  const generate = useMutation({
    mutationFn: () => fetchers.affiliateGenerate(3),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['aff-drafts'] });
      qc.invalidateQueries({ queryKey: ['aff-candidates'] });
    },
  });

  const publish = useMutation({
    mutationFn: (args: { id: string; override?: boolean }) =>
      fetchers.affiliatePublish(args.id, args.override),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['aff-drafts'] });
      qc.invalidateQueries({ queryKey: ['aff-report'] });
      qc.invalidateQueries({ queryKey: ['aff-health'] });
    },
  });

  const reject = useMutation({
    mutationFn: (args: { ids: string[] }) =>
      fetchers.affiliateReject(args.ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['aff-drafts'] }),
  });

  const pending = (drafts.data ?? []).filter((d: any) => !d.published);
  const h = health.data ?? {};
  const r = report.data ?? {};

  const credRows = [
    { label: 'Model', value: h.model ?? '—', ok: true },
    { label: 'Rootsys key', value: h.rootsys_key ?? '—', ok: h.rootsys_key === 'ready' },
    {
      label: 'Shopee API',
      value: (h.shopee_api ?? '—').replace('shopee api: ', ''),
      ok: String(h.shopee_api ?? '').includes('OK'),
    },
    {
      label: 'Threads API',
      value: (h.threads_api ?? '—').replace('threads token ', ''),
      ok: String(h.threads_api ?? '').includes('OK'),
    },
    {
      label: 'Approval',
      value: h.approval ?? '—',
      ok: String(h.approval ?? '').includes('required'),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Affiliate Bot</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              candidates.refetch();
              qc.invalidateQueries({ queryKey: ['aff-topics'] });
            }}
            disabled={candidates.isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
          >
            {candidates.isFetching ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            Discover
          </button>
          <button
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {generate.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Megaphone size={14} />
            )}
            Generate Drafts
          </button>
        </div>
      </div>

      {generate.isError && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
          <div className="font-semibold text-amber-400 mb-1">
            Draft generation did not complete
          </div>
          <div className="text-[var(--text-secondary)]">
            {(generate.error as any)?.message ?? 'Unknown error'}
          </div>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={FileText}
          label="Pending Drafts"
          value={pending.length}
          sub={`${(drafts.data ?? []).length} total generated`}
        />
        <StatCard
          icon={Radio}
          label="Posts Today"
          value={`${h.today?.posts ?? 0}`}
          sub={`${h.today?.replies ?? 0} replies`}
        />
        <StatCard
          icon={ShoppingBag}
          label="Items Promoted"
          value={h.totals?.items_promoted ?? 0}
          sub={`${r.conversion_count ?? 0} conversions`}
        />
        <StatCard
          icon={Coins}
          label="Commission"
          value={`RM${(r.total_commission ?? 0).toFixed(2)}`}
          sub={r.conversion_error ? 'report unavailable' : 'from conversion API'}
        />
      </div>

      {/* Credentials */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
          Pipeline Credentials
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {credRows.map((c) => (
            <div
              key={c.label}
              className="rounded-lg border border-[var(--border)] p-3 bg-[var(--bg-tertiary)]"
            >
              <div className="text-xs text-[var(--text-secondary)] mb-1">
                {c.label}
              </div>
              <div
                className={`text-sm font-medium truncate ${c.ok ? 'text-green-400' : 'text-amber-400'}`}
                title={c.value}
              >
                {c.value}
              </div>
            </div>
          ))}
        </div>
        {h.raw && (
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
              raw diagnostics
            </summary>
            <pre className="mt-2 p-3 rounded-lg bg-[var(--bg-tertiary)] overflow-x-auto text-[var(--text-secondary)] whitespace-pre-wrap">
              {h.raw}
            </pre>
          </details>
        )}
      </div>

      {/* Weekly ramp quota - the number that protects the account */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)]">
            Weekly Ramp Quota
          </h2>
          <span className="text-xs text-[var(--text-secondary)]">
            week {governor.data?.week ?? '—'} · {governor.data?.date ?? ''}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {(governor.data?.buckets ?? []).map((b: any) => {
            const pct = b.cap ? Math.min(100, (b.used / b.cap) * 100) : 0;
            const tone =
              pct >= 100 ? 'bg-red-500' : pct >= 75 ? 'bg-amber-500' : 'bg-green-500';
            return (
              <div
                key={b.key}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3"
              >
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-[var(--text-secondary)]">{b.name}</span>
                  <span className="font-mono">
                    {b.used}/{b.cap}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
                  <div
                    className={`h-full ${tone} transition-all`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          {!governor.data?.buckets?.length && (
            <div className="text-sm text-[var(--text-secondary)] col-span-3">
              Loading quota…
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-[var(--text-secondary)] mb-2">
              Reply risk — needs review ({governor.data?.review_queue?.length ?? 0})
            </div>
            <ul className="space-y-1.5 max-h-40 overflow-y-auto">
              {(governor.data?.review_queue ?? []).map((q: any, i: number) => (
                <li
                  key={i}
                  className="p-2 rounded-lg border border-amber-500/30 bg-amber-500/5 text-xs"
                >
                  <div className="font-medium mb-0.5">{q.comment}</div>
                  <div className="text-[var(--text-secondary)] font-mono">
                    {q.classification} · {(q.reasons ?? []).join(', ')}
                  </div>
                </li>
              ))}
              {!governor.data?.review_queue?.length && (
                <li className="text-xs text-[var(--text-secondary)]">
                  Nothing waiting on review.
                </li>
              )}
            </ul>
          </div>

          <div>
            <div className="text-xs text-[var(--text-secondary)] mb-2">
              Escalated — never answered (
              {governor.data?.escalations?.length ?? 0})
            </div>
            <ul className="space-y-1.5 max-h-40 overflow-y-auto">
              {(governor.data?.escalations ?? []).map((q: any, i: number) => (
                <li
                  key={i}
                  className="p-2 rounded-lg border border-red-500/30 bg-red-500/5 text-xs"
                >
                  <div className="font-medium mb-0.5">{q.comment}</div>
                  <div className="text-[var(--text-secondary)] font-mono">
                    {q.classification} · {(q.reasons ?? []).join(', ')}
                  </div>
                </li>
              ))}
              {!governor.data?.escalations?.length && (
                <li className="text-xs text-[var(--text-secondary)]">
                  No escalations.
                </li>
              )}
            </ul>
          </div>

          <div>
            <div className="text-xs text-[var(--text-secondary)] mb-2">
              Content mix (7-day)
            </div>
            <div className="text-xs space-y-1">
              {Object.entries(governor.data?.content_mix ?? {}).map(([k, v]: any) => (
                <div key={k} className="flex justify-between">
                  <span className="text-[var(--text-secondary)]">{k}</span>
                  <span className="font-mono">
                    {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                  </span>
                </div>
              ))}
              {!Object.keys(governor.data?.content_mix ?? {}).length && (
                <div className="text-[var(--text-secondary)]">
                  No mix data yet.
                </div>
              )}
            </div>
            <div className="mt-3 text-xs text-[var(--text-secondary)]">
              Comments answered:{' '}
              <span className="font-mono text-[var(--text-primary)]">
                {governor.data?.replied_count ?? 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Topics */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
            Live Topic Signal
          </h2>
          {topics.isLoading ? (
            <div className="text-sm text-[var(--text-secondary)]">Loading…</div>
          ) : topics.data?.length ? (
            <ul className="space-y-1.5 max-h-80 overflow-y-auto">
              {topics.data.map((t: any, i: number) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm py-1 border-b border-[var(--border)] last:border-0"
                >
                  <span
                    className={`mt-0.5 shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase ${
                      t.kind === 'trend'
                        ? 'bg-purple-500/10 text-purple-400'
                        : 'bg-blue-500/10 text-blue-400'
                    }`}
                  >
                    {t.kind}
                  </span>
                  <span className="flex-1 text-[var(--text-primary)]">{t.title}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-[var(--text-secondary)]">No topics</div>
          )}
        </div>

        {/* Candidates */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
            Product Candidates
          </h2>
          {candidates.isFetching ? (
            <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <Loader2 size={14} className="animate-spin" /> Querying Shopee Open API…
            </div>
          ) : candidates.data?.length ? (
            <ul className="space-y-2 max-h-80 overflow-y-auto">
              {candidates.data.map((c: any, i: number) => (
                <li
                  key={i}
                  className="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)]"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{c.name}</div>
                      <div className="text-xs text-[var(--text-secondary)] mt-0.5">
                        RM{c.price_min?.toFixed?.(2) ?? c.price_min} ·{' '}
                        {(c.commission_rate * 100).toFixed(1)}% ·{' '}
                        {c.sales} sold · {c.rating?.toFixed?.(1)}*
                      </div>
                      <div className="text-xs text-[var(--text-secondary)] mt-0.5 truncate">
                        {c.topic}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="font-mono text-sm font-semibold text-[var(--accent)]">
                        {c.fit?.toFixed?.(1)}
                      </div>
                      <div className="text-[10px] text-[var(--text-secondary)]">fit</div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-[var(--text-secondary)]">
              Press <span className="font-mono">Discover</span> to query the Shopee
              affiliate Open API. Needs <span className="font-mono">SHOPEE_API_APP_ID</span>{' '}
              and <span className="font-mono">SHOPEE_API_SECRET</span>.
            </div>
          )}
        </div>
      </div>

      {/* Drafts */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)]">
            Draft Queue
          </h2>
          {pending.length > 0 && (
            <button
              onClick={() =>
                reject.mutate({ ids: pending.map((d: any) => d.id) })
              }
              disabled={reject.isPending}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg border border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
            >
              <X size={12} /> Reject All
            </button>
          )}
        </div>

        {drafts.isLoading ? (
          <div className="text-sm text-[var(--text-secondary)]">Loading…</div>
        ) : pending.length ? (
          <div className="space-y-3">
            {pending.map((d: any) => {
              const isOpen = expanded === d.id;
              const flags: string[] = d.flags ?? [];
              return (
                <div
                  key={d.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] overflow-hidden"
                >
                  <div className="p-3.5">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-[var(--text-secondary)] truncate">
                          {d.product_name}
                        </div>
                        <div className="text-[10px] text-[var(--text-secondary)] mt-0.5 uppercase tracking-wide">
                          {d.archetype} · {d.topic}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <ScoreBadge score={d.score ?? 0} flags={flags} />
                        <button
                          onClick={() => setExpanded(isOpen ? null : d.id)}
                          className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                        >
                          {isOpen ? 'less' : 'more'}
                        </button>
                      </div>
                    </div>

                    {flags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {flags.map((f: string) => (
                          <span
                            key={f}
                            className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-red-500/10 text-red-400"
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="text-sm whitespace-pre-wrap text-[var(--text-primary)]">
                      {isOpen
                        ? d.text
                        : (d.text ?? '').slice(0, 180) +
                          ((d.text ?? '').length > 180 ? '…' : '')}
                    </div>

                    {isOpen && d.link && (
                      <a
                        href={d.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 mt-2 text-xs font-mono text-[var(--accent)] hover:underline"
                      >
                        {d.link} <ExternalLink size={11} />
                      </a>
                    )}

                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() =>
                          publish.mutate({ id: d.id, override: flags.length > 0 })
                        }
                        disabled={publish.isPending}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                      >
                        {publish.isPending ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Play size={12} />
                        )}
                        Publish
                      </button>
                      <button
                        onClick={() => reject.mutate({ ids: [d.id] })}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors"
                      >
                        <X size={12} /> Reject
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-sm text-[var(--text-secondary)]">
            No pending drafts. Press <span className="font-mono">Generate Drafts</span>{' '}
            to run topics → products → Manglish generation.
          </div>
        )}
      </div>

      {/* Research + performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4 flex items-center gap-2">
            <BookOpen size={14} /> Research Corpus
          </h2>
          {research.data?.files?.length ? (
            <>
              <ul className="space-y-1.5 mb-4">
                {research.data.files.map((f: any) => (
                  <li key={f.name} className="flex justify-between text-sm">
                    <span className="font-mono text-xs">{f.name}</span>
                    <span className="text-xs text-[var(--text-secondary)]">
                      {f.lines} lines · {(f.bytes / 1024).toFixed(1)}KB
                    </span>
                  </li>
                ))}
              </ul>
              <div className="text-xs text-[var(--text-secondary)] mb-2">
                Top corpus word frequencies
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(research.data.top_lexicon ?? {})
                  .slice(0, 18)
                  .map(([w, c]: any) => (
                    <span
                      key={w}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-tertiary)] border border-[var(--border)]"
                    >
                      {w} <span className="text-[var(--text-secondary)]">{c}</span>
                    </span>
                  ))}
              </div>
            </>
          ) : (
            <div className="text-sm text-[var(--text-secondary)]">No corpus data</div>
          )}
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">
            Performance by Archetype
          </h2>
          {Object.keys(r.by_archetype ?? {}).length ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-secondary)] border-b border-[var(--border)]">
                  <th className="py-2 pr-4 font-medium">Archetype</th>
                  <th className="py-2 px-4 font-medium text-right">Posts</th>
                  <th className="py-2 pl-4 font-medium text-right">Avg Score</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(r.by_archetype ?? {}).map(([k, v]: any) => (
                  <tr key={k} className="border-b border-[var(--border)] last:border-0">
                    <td className="py-2 pr-4">{k}</td>
                    <td className="py-2 px-4 text-right">{v.count}</td>
                    <td className="py-2 pl-4 text-right font-mono">{v.avg_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-sm text-[var(--text-secondary)]">
              No published posts yet. Publish a draft to start tracking which
              archetype performs.
            </div>
          )}
          {r.conversion_error && (
            <div className="mt-3 text-xs text-amber-400">{r.conversion_error}</div>
          )}
        </div>
      </div>
    </div>
  );
}
