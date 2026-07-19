'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useRef,
} from 'react';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';

/* ── Types ─────────────────────────────────────────────────────────────── */

type ToastType = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

/* ── Context ───────────────────────────────────────────────────────────── */

const ToastContext = createContext<ToastContextValue | null>(null);

/* ── Hook ──────────────────────────────────────────────────────────────── */

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}

/* ── Icons ─────────────────────────────────────────────────────────────── */

const ICONS: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={18} className="text-[var(--success)] shrink-0" />,
  error: <AlertCircle size={18} className="text-[var(--error)] shrink-0" />,
  info: <Info size={18} className="text-[var(--accent)] shrink-0" />,
};

const BORDER_COLORS: Record<ToastType, string> = {
  success: 'border-l-[var(--success)]',
  error: 'border-l-[var(--error)]',
  info: 'border-l-[var(--accent)]',
};

/* ── Provider ──────────────────────────────────────────────────────────── */

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const add = useCallback((type: ToastType, message: string) => {
    const id = ++counter.current;
    setToasts((prev) => [...prev, { id, type, message }]);
    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const ctx: ToastContextValue = {
    success: (msg) => add('success', msg),
    error: (msg) => add('error', msg),
    info: (msg) => add('info', msg),
  };

  const dismiss = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}

      {/* Toast container — bottom-right */}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`
              pointer-events-auto flex items-center gap-3
              min-w-[280px] max-w-sm px-4 py-3
              rounded-lg border border-[var(--border)]
              bg-[var(--bg-secondary)] shadow-lg
              border-l-4 ${BORDER_COLORS[toast.type]}
              animate-[slideIn_0.2s_ease-out]
            `}
            style={{
              animation: 'slideIn 0.2s ease-out',
            }}
          >
            {ICONS[toast.type]}
            <span className="text-sm flex-1">{toast.message}</span>
            <button
              onClick={() => dismiss(toast.id)}
              className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors shrink-0"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
