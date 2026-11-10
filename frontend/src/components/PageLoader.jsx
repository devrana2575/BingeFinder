/**
 * Route-level loading fallback used while a lazily-loaded page chunk is
 * fetched. Mirrors the app shell so navigation never flashes a blank screen.
 *
 * Pass `fullScreen` when there is no app shell yet (initial auth check or a
 * guest being redirected to /login).
 */
export default function PageLoader({ fullScreen = false }) {
  if (fullScreen) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-6" role="status" aria-live="polite" aria-label="Loading">
        <div className="flex flex-col items-center gap-3">
          <span className="text-xl font-bold tracking-tight text-text" style={{ fontFamily: 'Sora, sans-serif' }}>
            Binge<span className="text-accent">Finder</span>
          </span>
          <span className="h-1 w-36 overflow-hidden rounded-full bg-surface-2">
            <span className="block h-full w-1/2 skeleton" />
          </span>
        </div>
      </div>
    );
  }

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
