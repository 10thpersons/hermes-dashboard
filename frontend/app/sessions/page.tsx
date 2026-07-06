"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchers } from "@/lib/api";
import Link from "next/link";
import { useState } from "react";
import { Search } from "lucide-react";

export default function SessionsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 30;

  const { data, isLoading } = useQuery({
    queryKey: ["sessions", search, page],
    queryFn: () => fetchers.sessions(limit, page * limit, search || undefined),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Sessions</h1>

      <div className="relative max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
        <input
          type="text"
          placeholder="Search sessions..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="w-full pl-9 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
        />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--text-secondary)]">
              <th className="px-4 py-3 font-medium">Session ID</th>
              <th className="px-4 py-3 font-medium">Source</th>
              <th className="px-4 py-3 font-medium">Model</th>
              <th className="px-4 py-3 font-medium">Messages</th>
              <th className="px-4 py-3 font-medium">Date</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-[var(--text-secondary)]">Loading...</td></tr>
            ) : data?.sessions?.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-[var(--text-secondary)]">No sessions found</td></tr>
            ) : (
              data?.sessions?.map((s: any) => (
                <tr key={s.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/sessions/${s.id}`} className="text-[var(--accent)] hover:underline font-mono text-xs">
                      {s.id.length > 24 ? s.id.slice(0, 24) + "..." : s.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">{s.source || "—"}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] text-xs">{s.model || "—"}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">{s.message_count ?? "—"}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {s.started_at ? new Date(s.started_at * 1000).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--text-secondary)]">{data?.total ?? 0} total</span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1 text-sm rounded border border-[var(--border)] disabled:opacity-40 hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            Prev
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!data || (page + 1) * limit >= data.total}
            className="px-3 py-1 text-sm rounded border border-[var(--border)] disabled:opacity-40 hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
