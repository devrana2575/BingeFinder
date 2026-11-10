/**
 * Route-level loading fallback used while a lazily-loaded page chunk is
 * fetched. Mirrors the app shell so navigation never flashes a blank screen.
 */
export default function PageLoader() {
  return (
    <div className="p-4 sm:p-6 lg:p-8" role="status" aria-live="polite" aria-label="Loading page">
      <div className="max-w-7xl mx-auto space-y-4">
        <div className="h-8 w-64 skeleton" />
        <div className="h-4 w-96 max-w-full skeleton" />
        <div className="card-grid mt-8">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-xl overflow-hidden">
              <div className="aspect-[2/3] skeleton" />
              <div className="p-3 space-y-2">
                <div className="h-4 w-3/4 skeleton" />
                <div className="h-8 w-full skeleton rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
