"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchers } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { Activity, MessageSquare, Clock, HardDrive } from "lucide-react";
import Link from "next/link";

export default function OverviewPage() {
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: fetchers.systemHealth });
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: () => fetchers.sessions(5) });
  const { data: cron } = useQuery({ queryKey: ["cron"], queryFn: fetchers.cronJobs });

  const disk = health?.disk;
  const services = health?.services || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Activity} label="Uptime" value={health?.uptime || "—"} sub={health?.hostname} />
        <StatCard icon={HardDrive} label="Disk" value={disk?.percent || "—"} sub={disk ? `${disk.used} / ${disk.total}` : undefined} />
        <StatCard icon={MessageSquare} label="Sessions" value={sessions?.total ?? "—"} />
        <StatCard icon={Clock} label="Cron Jobs" value={Array.isArray(cron) ? cron.length : "—"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Services</h2>
          <div className="space-y-3">
            {Object.entries(services).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between">
                <span className="text-sm">{name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  status === "active" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
                }`}>
                  {String(status)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Recent Sessions</h2>
          <div className="space-y-2">
            {sessions?.sessions?.map((s: any) => (
              <Link key={s.id} href={`/sessions/${s.id}`} className="flex items-center justify-between py-1.5 border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-tertiary)] transition-colors rounded px-1">
                <span className="text-sm font-mono truncate max-w-[200px]">{s.id}</span>
                <span className="text-xs text-[var(--text-secondary)]">{s.source}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
