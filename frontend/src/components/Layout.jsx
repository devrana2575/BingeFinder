import { Suspense, useState, useEffect, useCallback, useRef } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import PageLoader from './PageLoader';
import { useAuth } from '../context/AuthContext';

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { loading } = useAuth();
  const location = useLocation();
  const sidebarRef = useRef(null);
  const closeMenu = useCallback(() => setMobileOpen(false), []);

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const handleKey = (e) => { if (e.key === 'Escape') setMobileOpen(false); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [mobileOpen]);

  return (
    <div className="flex min-h-screen bg-bg">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-accent focus:text-bg focus:rounded-lg focus:font-semibold">
        Skip to main content
      </a>

      <div className="hidden lg:block fixed inset-y-0 left-0 z-30 w-60">
        <Sidebar />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={closeMenu}>
          <div className="absolute inset-0 bg-black/60" />
          <div ref={sidebarRef} className="relative z-50 h-full" onClick={e => e.stopPropagation()}>
            <Sidebar onNavigate={closeMenu} />
          </div>
        </div>
      )}

      <main id="main-content" className="flex-1 min-w-0 lg:ml-60">
        <div className="lg:hidden sticky top-0 z-30 bg-bg/90 backdrop-blur-sm border-b border-border px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 -ml-2 rounded-lg hover:bg-surface text-text-secondary"
            aria-label="Open navigation menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <Link to="/" className="text-sm font-bold text-text" style={{ fontFamily: 'Sora, sans-serif' }}>
            BingeFinder
          </Link>
        </div>

        <div className="p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">
            {loading ? (
              <div className="space-y-4">
                <div className="h-8 w-64 skeleton" />
                <div className="h-4 w-96 skeleton" />
                <div className="card-grid mt-8">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="bg-surface border border-border rounded-xl overflow-hidden">
                      <div className="aspect-[2/3] skeleton" />
                      <div className="p-3 space-y-2"><div className="h-4 w-3/4 skeleton" /><div className="h-8 w-full skeleton rounded-lg" /></div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="fade-in">
                <Suspense fallback={<PageLoader />}>
                  <Outlet />
                </Suspense>
              </div>
            )}

            <footer className="mt-12 pt-6 pb-2 border-t border-border text-[11px] leading-relaxed text-text-muted flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <p>© {new Date().getFullYear()} BingeFinder. All rights reserved.</p>
              <p>
                This product uses the TMDb API but is not endorsed or certified by TMDb.
              </p>
            </footer>
          </div>
        </div>
      </main>
    </div>
  );
}
