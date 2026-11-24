export default function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded bg-slate-200 ${className}`} aria-hidden="true" />;
}

export function TableSkeleton({ rows = 4 }) {
  return (
    <div
      className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm"
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-4">
          <Skeleton className="h-9 w-9 shrink-0 rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-1/5" />
          </div>
          <Skeleton className="hidden h-3.5 w-16 sm:block" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function CardGridSkeleton({ cards = 3 }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" role="status" aria-label="Loading">
      {Array.from({ length: cards }).map((_, i) => (
        <div key={i} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}
