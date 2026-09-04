export function SkeletonCard() {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="aspect-[2/3] skeleton" />
      <div className="p-3 space-y-2">
        <div className="h-4 w-3/4 skeleton" />
        <div className="h-3 w-1/2 skeleton" />
        <div className="flex gap-1">
          <div className="h-4 w-10 skeleton rounded" />
          <div className="h-4 w-12 skeleton rounded" />
        </div>
        <div className="h-8 w-full skeleton rounded-lg" />
      </div>
    </div>
  );
}

export function SkeletonGrid({ count = 6 }) {
  return (
    <div className="card-grid">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonText({ lines = 3, className = '' }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 skeleton" style={{ width: `${85 - i * 15}%` }} />
      ))}
    </div>
  );
}
