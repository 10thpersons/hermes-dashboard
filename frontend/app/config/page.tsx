'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchers } from '@/lib/api';
import { useState, useEffect } from 'react';
import { Save, Check } from 'lucide-react';

export default function ConfigPage() {
  const queryClient = useQueryClient();
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: fetchers.config,
  });
  const [yaml, setYaml] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config) setYaml(JSON.stringify(config, null, 2));
  }, [config]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(yaml);
      return fetchers.updateConfig(parsed);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Configuration</h1>
        <span className="text-xs text-[var(--text-secondary)]">
          JSON format
        </span>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
        >
          {saved ? <Check size={16} /> : <Save size={16} />}
          {saved ? 'Saved' : saveMutation.isPending ? 'Saving...' : 'Save'}
        </button>
      </div>

      {saveMutation.isError && (
        <div className="text-sm text-red-400 bg-red-400/10 px-4 py-2 rounded-lg">
          {(saveMutation.error as Error).message}
        </div>
      )}

      {isLoading ? (
        <div className="text-[var(--text-secondary)]">Loading config...</div>
      ) : (
        <textarea
          value={yaml}
          onChange={(e) => setYaml(e.target.value)}
          className="w-full h-[70vh] rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5 font-mono text-sm leading-relaxed focus:outline-none focus:border-[var(--accent)] transition-colors resize-none"
          spellCheck={false}
        />
      )}
    </div>
  );
}
