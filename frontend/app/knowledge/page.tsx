'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { MarkdownViewer } from '@/components/markdown-viewer';
import { useState } from 'react';

type Tab = 'memory' | 'skills' | 'souls';

export default function KnowledgePage() {
  const [tab, setTab] = useState<Tab>('memory');
  const [selected, setSelected] = useState<string | null>(null);

  const { data: memory } = useQuery({
    queryKey: ['memory'],
    queryFn: fetchers.memory,
    enabled: tab === 'memory',
  });
  const { data: skills } = useQuery({
    queryKey: ['skills'],
    queryFn: fetchers.skills,
    enabled: tab === 'skills',
  });
  const { data: souls } = useQuery({
    queryKey: ['souls'],
    queryFn: fetchers.souls,
    enabled: tab === 'souls',
  });

  const items = tab === 'memory' ? memory : tab === 'skills' ? skills : souls;
  const selectedItem = items?.find((i: any) => i.name === selected);

  const tabs: { key: Tab; label: string }[] = [
    { key: 'memory', label: 'Memory' },
    { key: 'skills', label: 'Skills' },
    { key: 'souls', label: 'SOULs' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Knowledge Base</h1>

      <div className="flex gap-1 border-b border-[var(--border)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => {
              setTab(t.key);
              setSelected(null);
            }}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] max-h-[70vh] overflow-y-auto">
          {items?.length === 0 ? (
            <div className="p-4 text-sm text-[var(--text-secondary)]">
              No items found
            </div>
          ) : (
            items?.map((item: any) => (
              <button
                key={item.name}
                onClick={() => setSelected(item.name)}
                className={`w-full text-left px-4 py-3 border-b border-[var(--border)] last:border-0 text-sm transition-colors ${
                  selected === item.name
                    ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                    : 'hover:bg-[var(--bg-tertiary)]'
                }`}
              >
                <div className="font-medium">{item.name}</div>
                {item.relative && (
                  <div className="text-xs text-[var(--text-secondary)] mt-0.5">
                    {item.relative}
                  </div>
                )}
              </button>
            ))
          )}
        </div>

        <div className="lg:col-span-2 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5 min-h-[300px] max-h-[70vh] overflow-y-auto">
          {selectedItem ? (
            <>
              <MarkdownViewer content={selectedItem.content} />
              {selectedItem.size > 10000 && (
                <div className="mt-4 text-xs text-[var(--warning)] border-t border-[var(--border)] pt-3">
                  ⚠ Content truncated. Full size:{' '}
                  {selectedItem.size.toLocaleString()} chars. Showing first
                  10,000.
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-[var(--text-secondary)] flex items-center justify-center h-full">
              Select an item to view
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
