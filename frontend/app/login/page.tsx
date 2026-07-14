'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        router.push('/');
        router.refresh();
      } else {
        setError('Wrong password. Try again.');
      }
    } catch {
      setError('Connection failed. Is the server running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
      <div className="w-full max-w-sm px-4">
        <div className="mb-8 text-center">
          <span className="font-mono text-2xl font-bold tracking-widest text-[var(--accent)]">
            HERMES
          </span>
          <p className="text-sm text-[var(--text-secondary)] mt-2">
            Enter your dashboard password
          </p>
        </div>
        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6 space-y-4"
        >
          <div>
            <label className="block text-xs text-[var(--text-secondary)] mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              required
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>
          {error && <p className="text-xs text-[var(--error)]">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
