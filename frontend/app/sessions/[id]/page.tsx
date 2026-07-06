"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchers } from "@/lib/api";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["session", id],
    queryFn: () => fetchers.sessionDetail(id),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/sessions" className="p-1.5 rounded hover:bg-[var(--bg-tertiary)] transition-colors">
          <ArrowLeft size={18} />
        </Link>
        <h1 className="text-xl font-bold truncate">{id}</h1>
      </div>

      {isLoading ? (
        <div className="text-[var(--text-secondary)]">Loading messages...</div>
      ) : (
        <div className="space-y-3">
          {data?.messages?.map((msg: any) => {
            const isUser = msg.role === "user";
            return (
              <div key={msg.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[75%] rounded-xl px-4 py-3 text-sm ${
                    isUser
                      ? "bg-[var(--accent)]/15 border border-[var(--accent)]/30"
                      : "bg-[var(--bg-secondary)] border border-[var(--border)]"
                  }`}
                >
                  <div className="text-xs text-[var(--text-secondary)] mb-1.5 font-medium">
                    {msg.role.toUpperCase()}
                  </div>
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                  {msg.tool_calls && (
                    <div className="mt-2 text-xs text-[var(--text-secondary)] border-t border-[var(--border)] pt-2">
                      🔧 Tool calls present
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
