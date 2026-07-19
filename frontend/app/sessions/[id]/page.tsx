'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Search,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Wrench,
  User,
  Bot,
} from 'lucide-react';
import { useState, useRef, useEffect, useCallback } from 'react';
import { Skeleton } from '@/components/skeleton';

/* ── Types ─────────────────────────────────────────────────────────────── */

interface Message {
  id: number;
  role: string;
  content: string;
  tool_calls?: string | null;
  tool_name?: string | null;
  timestamp?: string | null;
  token_count?: number | null;
}

/* ── Role badge colors ─────────────────────────────────────────────────── */

const ROLE_STYLES: Record<string, { bg: string; border: string; text: string; icon: typeof User }> = {
  user: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', icon: User },
  assistant: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: Bot },
  tool: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', icon: Wrench },
};

/* ── Copy button ───────────────────────────────────────────────────────── */

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors opacity-0 group-hover:opacity-100"
      title="Copy message"
    >
      {copied ? <Check size={13} className="text-[var(--success)]" /> : <Copy size={13} />}
    </button>
  );
}

/* ── Tool calls display (collapsible) ──────────────────────────────────── */

function ToolCallDisplay({ toolCalls }: { toolCalls: string }) {
  const [expanded, setExpanded] = useState(false);
  let parsed: any = null;
  try {
    parsed = JSON.parse(toolCalls);
  } catch {
    parsed = null;
  }

  const calls = Array.isArray(parsed) ? parsed : parsed ? [parsed] : [];

  if (calls.length === 0) {
    return (
      <div className="mt-2 text-xs text-[var(--text-secondary)] border-t border-[var(--border)] pt-2 font-mono">
        🔧 Tool calls present (unparseable)
      </div>
    );
  }

  return (
    <div className="mt-2 border-t border-[var(--border)] pt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 transition-colors"
      >
        {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <Wrench size={12} />
        {calls.length} tool call{calls.length > 1 ? 's' : ''}
      </button>
      {expanded && (
        <div className="mt-2 space-y-2">
          {calls.map((call: any, idx: number) => (
            <div
              key={idx}
              className="rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] p-3 text-xs"
            >
              <div className="font-medium text-purple-400 mb-1">
                {call.function?.name || call.name || `Tool #${idx + 1}`}
              </div>
              {call.function?.arguments && (
                <pre className="text-[var(--text-secondary)] font-mono whitespace-pre-wrap break-words max-h-40 overflow-auto">
                  {typeof call.function.arguments === 'string'
                    ? call.function.arguments
                    : JSON.stringify(call.function.arguments, null, 2)}
                </pre>
              )}
              {call.result && (
                <div className="mt-2 pt-2 border-t border-[var(--border)]">
                  <div className="text-[var(--text-secondary)] mb-1">Result:</div>
                  <pre className="text-[var(--text-secondary)] font-mono whitespace-pre-wrap break-words max-h-40 overflow-auto">
                    {typeof call.result === 'string'
                      ? call.result
                      : JSON.stringify(call.result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Single message bubble ─────────────────────────────────────────────── */

function MessageBubble({ msg }: { msg: Message }) {
  const style = ROLE_STYLES[msg.role] || ROLE_STYLES.assistant;
  const Icon = style.icon;

  const timestamp = msg.timestamp
    ? new Date(msg.timestamp).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} group`}>
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 text-sm border ${style.bg} ${style.border}`}
      >
        {/* Header: role badge + timestamp + copy */}
        <div className="flex items-center justify-between gap-3 mb-1.5">
          <div className="flex items-center gap-1.5">
            <Icon size={13} className={style.text} />
            <span className={`text-xs font-medium ${style.text}`}>
              {msg.role.toUpperCase()}
            </span>
            {msg.tool_name && (
              <span className="text-xs text-[var(--text-secondary)] font-mono">
                ({msg.tool_name})
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {msg.token_count != null && msg.token_count > 0 && (
              <span className="text-[10px] text-[var(--text-secondary)] font-mono">
                {msg.token_count.toLocaleString()} tok
              </span>
            )}
            {timestamp && (
              <span className="text-[10px] text-[var(--text-secondary)]">{timestamp}</span>
            )}
            <CopyButton text={msg.content || ''} />
          </div>
        </div>

        {/* Content */}
        <div className="whitespace-pre-wrap break-words leading-relaxed">
          {msg.content || <span className="text-[var(--text-secondary)] italic">[empty]</span>}
        </div>

        {/* Tool calls */}
        {msg.tool_calls && <ToolCallDisplay toolCalls={msg.tool_calls} />}
      </div>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────────────── */

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ['session', id],
    queryFn: () => fetchers.sessionDetail(id),
  });

  const [search, setSearch] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const messages: Message[] = data?.messages || [];

  // Filter messages by search term
  const filtered = search.trim()
    ? messages.filter((m) =>
        (m.content || '').toLowerCase().includes(search.toLowerCase()) ||
        (m.role || '').toLowerCase().includes(search.toLowerCase()) ||
        (m.tool_name || '').toLowerCase().includes(search.toLowerCase())
      )
    : messages;

  // Auto-scroll to bottom on initial load
  useEffect(() => {
    if (messages.length > 0 && !search) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, search]);

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-4 flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/sessions"
            className="p-1.5 rounded hover:bg-[var(--bg-tertiary)] transition-colors shrink-0"
          >
            <ArrowLeft size={18} />
          </Link>
          <h1 className="text-xl font-bold truncate font-mono">{id}</h1>
        </div>
        <div className="flex items-center gap-3">
          {/* Search within messages */}
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
            />
            <input
              type="text"
              placeholder="Search messages..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] text-xs focus:outline-none focus:border-[var(--accent)] transition-colors w-48"
            />
          </div>
          {messages.length > 0 && (
            <span className="text-xs text-[var(--text-secondary)] shrink-0">
              {search ? `${filtered.length}/${messages.length}` : `${messages.length}`} messages
            </span>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4 space-y-3 min-h-0">
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
                <div className="max-w-[75%] space-y-2 rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] p-4">
                  <Skeleton className="w-16 h-3" />
                  <Skeleton className="w-full h-4" />
                  <Skeleton className="w-3/4 h-4" />
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)]">
            {search ? 'No messages match your search' : 'No messages in this session'}
          </div>
        ) : (
          filtered.map((msg) => <MessageBubble key={msg.id} msg={msg} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
