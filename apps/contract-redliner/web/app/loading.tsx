export default function Loading() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-56 animate-pulse rounded-lg bg-ink-200/70" />
      <div className="h-4 w-80 animate-pulse rounded bg-ink-200/50" />
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="h-28 animate-pulse rounded-2xl bg-white/70" />
        <div className="h-28 animate-pulse rounded-2xl bg-white/70" />
        <div className="h-28 animate-pulse rounded-2xl bg-white/70" />
      </div>
      <div className="h-64 animate-pulse rounded-2xl bg-white/70" />
    </div>
  );
}