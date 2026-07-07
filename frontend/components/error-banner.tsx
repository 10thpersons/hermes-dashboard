export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-[var(--error)]/30 bg-[var(--error)]/10 px-4 py-3 text-sm text-[var(--error)]">
      {message}
    </div>
  );
}
