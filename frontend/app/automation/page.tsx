"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchers } from "@/lib/api";

export default function AutomationPage() {
  const queryClient = useQueryClient();
  const { data: jobs, isLoading } = useQuery({ queryKey: ["cron"], queryFn: fetchers.cronJobs });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => fetchers.toggleCron(id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cron"] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Automation</h1>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--text-secondary)]">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Schedule</th>
              <th className="px-4 py-3 font-medium">Model</th>
              <th className="px-4 py-3 font-medium text-center">Enabled</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-[var(--text-secondary)]">Loading...</td></tr>
            ) : !Array.isArray(jobs) || jobs.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-[var(--text-secondary)]">No cron jobs</td></tr>
            ) : (
              jobs.map((job: any) => (
                <tr key={job.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors">
                  <td className="px-4 py-3 font-medium">{job.name || job.id}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">{job.schedule}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] text-xs">{job.model || "—"}</td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => toggleMutation.mutate({ id: job.id, enabled: !job.enabled })}
                      className={`relative w-10 h-5 rounded-full transition-colors ${
                        job.enabled ? "bg-[var(--accent)]" : "bg-[var(--border)]"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                          job.enabled ? "left-5.5 translate-x-0" : "left-0.5"
                        }`}
                      />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
