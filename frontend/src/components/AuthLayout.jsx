import { Link, Outlet } from 'react-router-dom';
import { t } from '../i18n';

/**
 * Minimal shell for login/signup. Deliberately has no sidebar or browse
 * navigation: unauthenticated visitors only see the auth entry points.
 */
export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <header className="p-5 sm:p-6">
        <Link to="/login" className="inline-block" aria-label="BingeFinder">
          <span className="text-xl font-bold tracking-tight text-text" style={{ fontFamily: 'Sora, sans-serif' }}>
            Binge<span className="text-accent">Finder</span>
          </span>
          <span className="block text-[10px] uppercase tracking-[0.14em] text-text-muted mt-0.5">
            {t('hero.tagline')}
          </span>
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm">
          <Outlet />
        </div>
      </main>

      <footer className="px-4 py-4 text-center text-[11px] leading-relaxed text-text-muted border-t border-border">
        This product uses the TMDb API but is not endorsed or certified by TMDb.
      </footer>
    </div>
  );
}
