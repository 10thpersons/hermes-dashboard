'use client';

/** Reusable loading skeleton components using Tailwind animate-pulse. */

/** Basic skeleton pulse element */
export function Skeleton({
  className = '',
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`animate-pulse bg-[var(--border)] rounded ${className}`}
      style={style}
    />
  );
}

/** Skeleton placeholder for stat cards */
export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4 md:p-5">
      <Skeleton className="w-20 h-4 mb-3" />
      <Skeleton className="w-24 h-8 mb-2" />
      <Skeleton className="w-32 h-3" />
    </div>
  );
}

/** Skeleton placeholder for table rows */
export function SkeletonTable({
  rows = 5,
  cols = 4,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] overflow-hidden">
      {/* Header */}
      <div className="border-b border-[var(--border)] px-4 py-3 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton
            key={i}
            className="h-4 flex-1"
          />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, row) => (
        <div
          key={row}
          className="px-4 py-3 border-b border-[var(--border)] last:border-0 flex gap-4"
        >
          {Array.from({ length: cols }).map((_, col) => (
            <Skeleton
              key={col}
              className="h-4 flex-1"
              style={{ width: `${60 + Math.random() * 40}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Skeleton placeholder for chart areas */
export function SkeletonChart({ height = 'h-48' }: { height?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-5">
      <Skeleton className="w-40 h-4 mb-4" />
      <div className={`flex items-end gap-1 ${height}`}>
        {Array.from({ length: 30 }).map((_, i) => (
          <Skeleton
            key={i}
            className="flex-1 min-w-[8px] rounded-t"
            style={{ height: `${20 + Math.random() * 80}%` }}
          />
        ))}
      </div>
    </div>
  );
}

/** Full page skeleton with header + content area */
export function SkeletonPage() {
  return (
    <div className="space-y-6">
      <Skeleton className="w-48 h-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <SkeletonTable />
    </div>
  );
}
