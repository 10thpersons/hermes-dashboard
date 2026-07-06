"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchers } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { HardDrive, Activity, Server, Clock } from "lucide-react";

export default function SystemPage() {
  const { data: health, isLoading } = useQuery({ queryKey: ["health"], queryFn: fetchers.systemHealth });

  if (isLoading) return <div className="text-[var(--text-secondary)]">Loading...</div>;

  const disk = health?.disk || {};
  const services = health?.services || {};
  const hermes = health?.hermes || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">System Health</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Server} label="Hostname" value={health?.hostname || "—"} />
        <StatCard icon={Clock} label="Uptime" value={health?.uptime || "—"} />
        <StatCard icon={HardDrive} label="Disk Usage" value={disk.percent || "—"} sub={`${disk.used} / ${disk.total} (${disk.available} free)`} />
        <StatCard icon={Activity} label="Timestamp" value={health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : "—"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Services</h2>
          <div className="space-y-3">
            {Object.entries(services).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
                <span className="text-sm font-medium">{name}</span>
                <span className={`text-xs px-2.5 py-1 rounded-full ${
                  status === "active" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
                }`}>
                  {String(status)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Hermes Components</h2>
          <div className="space-y-3">
            {Object.entries(hermes).map(([name, ok]) => (
              <div key={name} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
                <span className="text-sm font-medium">{name.replace(/_/g, " ")}</span>
                <span className={`text-xs px-2.5 py-1 rounded-full ${
                  ok ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
                }`}>
                  {ok ? "OK" : "Missing"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
