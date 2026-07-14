'use client';
import { Fragment, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';

interface CronJob {
  id: string;
  name?: string;
  schedule?: string | { display?: string; expr?: string };
  schedule_display?: string;
  model?: string;
  enabled: boolean;
  last_run_time?: string | null;
  last_run_status?: string;
  last_run_at?: string | null;
  last_status?: string;
  output_file_count?: number;
  repeat?: { completed?: number };
}

interface CronOutput {
  job_id: string;
  filename: string;
  content: string;
  size: number;
  mtime_iso: string;
  truncated: boolean;
}

interface HistoryFile {
  filename: string;
  size: number;
  mtime: number;
  mtime_iso: string;
}

function fmtRelative(iso?: string | null): string {
  if (!iso) return 'never';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function scheduleLabel(job: CronJob): string {
  if (typeof job.schedule === 'string') return job.schedule;
  if (job.schedule?.display) return job.schedule.display;
  if (job.schedule?.expr) return job.schedule.expr;
  return job.schedule_display || '—';
}

function StatusBadge({ status }: { status?: string }) {
  const map: Record<string, string> = {
    success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/15 text-red-400 border-red-500/30',
    error: 'bg-red-500/15 text-red-400 border-red-500/30',
    ok: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    never: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
  };
  const label =
    status === 'success'
      ? 'success'
      : status === 'failed' || status === 'error'
        ? 'failed'
        : 'never';
  const cls = map[label] || map.never;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {label}
    </span>
  );
}

export default function AutomationPage() {
  const queryClient = useQueryClient();
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['cron'],
    queryFn: fetchers.cronJobs,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [viewModal, setViewModal] = useState<{
    jobId: string;
    filename?: string;
  } | null>(null);

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      fetchers.toggleCron(id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cron'] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Automation</h1>
        {Array.isArray(jobs) && jobs.length > 0 && (
          <span className="text-sm text-[var(--text-secondary)]">
            {jobs.length} jobs · {jobs.filter((j: CronJob) => j.enabled).length}{' '}
            active
          </span>
        )}
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--text-secondary)]">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Schedule</th>
              <th className="px-4 py-3 font-medium">Model</th>
              <th className="px-4 py-3 font-medium">Last Run</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-center">Enabled</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--text-secondary)]"
                >
                  Loading...
                </td>
              </tr>
            ) : !Array.isArray(jobs) || jobs.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--text-secondary)]"
                >
                  No cron jobs
                </td>
              </tr>
            ) : (
              jobs.map((job: CronJob) => {
                const isExpanded = expandedId === job.id;
                return (
                  <Fragment key={job.id}>
                    <tr
                      className={`border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors cursor-pointer ${isExpanded ? 'bg-[var(--bg-tertiary)]' : ''}`}
                      onClick={() => setExpandedId(isExpanded ? null : job.id)}
                    >
                      <td className="px-4 py-3 font-medium">
                        <div className="flex items-center gap-2">
                          <span className="text-[var(--text-secondary)] text-xs">
                            {isExpanded ? '▼' : '▶'}
                          </span>
                          <div>
                            <div>{job.name || job.id}</div>
                            <div className="text-xs text-[var(--text-secondary)] font-mono">
                              {job.id}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">
                        {scheduleLabel(job)}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] text-xs">
                        {job.model || '—'}
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] text-xs">
                        {fmtRelative(job.last_run_time ?? job.last_run_at)}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={job.last_run_status} />
                      </td>
                      <td
                        className="px-4 py-3 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() =>
                            toggleMutation.mutate({
                              id: job.id,
                              enabled: !job.enabled,
                            })
                          }
                          className={`relative w-10 h-5 rounded-full transition-colors ${
                            job.enabled
                              ? 'bg-[var(--accent)]'
                              : 'bg-[var(--border)]'
                          }`}
                        >
                          <span
                            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                              job.enabled
                                ? 'left-5.5 translate-x-0'
                                : 'left-0.5'
                            }`}
                          />
                        </button>
                      </td>
                      <td
                        className="px-4 py-3 text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() => setViewModal({ jobId: job.id })}
                          disabled={!job.output_file_count}
                          className="px-2.5 py-1 text-xs rounded-md border border-[var(--border)] bg-[var(--bg-tertiary)] hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          View Output
                          {job.output_file_count
                            ? ` (${job.output_file_count})`
                            : ''}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr
                        key={`${job.id}-expanded`}
                        className="bg-[var(--bg-tertiary)]"
                      >
                        <td
                          colSpan={7}
                          className="px-4 py-3"
                        >
                          <ExpandedPanel jobId={job.id} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {viewModal && (
        <OutputModal
          jobId={viewModal.jobId}
          initialFilename={viewModal.filename}
          onClose={() => setViewModal(null)}
        />
      )}
    </div>
  );
}

function ExpandedPanel({ jobId }: { jobId: string }) {
  const {
    data: output,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['cron-output', jobId],
    queryFn: () => fetchers.cronOutput(jobId),
    retry: false,
  });

  if (isLoading)
    return (
      <div className="text-sm text-[var(--text-secondary)] py-4">
        Loading latest output...
      </div>
    );
  if (error || !output)
    return (
      <div className="text-sm text-[var(--text-secondary)] py-4">
        No output available for this job.
      </div>
    );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-[var(--text-secondary)]">
        <span>
          Latest: <span className="font-mono">{output.filename}</span>
        </span>
        <span>
          {fmtSize(output.size)} · {fmtRelative(output.mtime_iso)}
        </span>
      </div>
      <pre className="max-h-80 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] p-3 text-xs font-mono whitespace-pre-wrap break-words">
        {output.content}
        {output.truncated && (
          <span className="text-[var(--text-secondary)]">
            \n\n[output truncated]
          </span>
        )}
      </pre>
    </div>
  );
}

function OutputModal({
  jobId,
  initialFilename,
  onClose,
}: {
  jobId: string;
  initialFilename?: string;
  onClose: () => void;
}) {
  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ['cron-history', jobId],
    queryFn: () => fetchers.cronHistory(jobId),
  });
  const [selectedFile, setSelectedFile] = useState<string | undefined>(
    initialFilename,
  );
  const { data: output, isLoading: outLoading } = useQuery({
    queryKey: ['cron-output-file', jobId, selectedFile],
    queryFn: () =>
      selectedFile
        ? fetchers.cronOutputFile(jobId, selectedFile)
        : fetchers.cronOutput(jobId),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl max-h-[85vh] rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold">
            Cron Output ·{' '}
            <span className="font-mono text-[var(--text-secondary)]">
              {jobId}
            </span>
          </h2>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-white transition-colors text-lg leading-none px-2"
          >
            ✕
          </button>
        </div>
        <div className="flex flex-1 min-h-0">
          {/* History sidebar */}
          <div className="w-56 shrink-0 border-r border-[var(--border)] overflow-y-auto">
            <div className="px-3 py-2 text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide border-b border-[var(--border)]">
              History {history ? `(${history.count})` : ''}
            </div>
            {histLoading ? (
              <div className="px-3 py-4 text-xs text-[var(--text-secondary)]">
                Loading...
              </div>
            ) : history?.files?.length ? (
              history.files.map((f: HistoryFile) => (
                <button
                  key={f.filename}
                  onClick={() => setSelectedFile(f.filename)}
                  className={`w-full text-left px-3 py-2 text-xs border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors ${
                    (selectedFile ?? history.files[0]?.filename) === f.filename
                      ? 'bg-[var(--bg-tertiary)] text-[var(--accent)]'
                      : ''
                  }`}
                >
                  <div className="font-mono truncate">{f.filename}</div>
                  <div className="text-[var(--text-secondary)] mt-0.5">
                    {fmtRelative(f.mtime_iso)} · {fmtSize(f.size)}
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-xs text-[var(--text-secondary)]">
                No output files
              </div>
            )}
          </div>
          {/* Content */}
          <div className="flex-1 min-w-0 flex flex-col">
            {outLoading ? (
              <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-secondary)]">
                Loading...
              </div>
            ) : output ? (
              <>
                <div className="px-4 py-2 text-xs text-[var(--text-secondary)] border-b border-[var(--border)] flex justify-between">
                  <span className="font-mono truncate">{output.filename}</span>
                  <span className="shrink-0 ml-2">{fmtSize(output.size)}</span>
                </div>
                <pre className="flex-1 overflow-auto p-4 text-xs font-mono whitespace-pre-wrap break-words">
                  {output.content}
                  {output.truncated && (
                    <span className="text-[var(--text-secondary)]">
                      {'\n\n[output truncated]'}
                    </span>
                  )}
                </pre>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-secondary)]">
                No output
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
