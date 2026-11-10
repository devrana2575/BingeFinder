import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { t } from '../i18n';

function NavGroup({ label, children }) {
  return (
    <div className="mb-5">
      <p className="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">{label}</p>
      <nav className="flex flex-col gap-0.5" aria-label={label}>
        {children}
      </nav>
    </div>
  );
}

export default function Sidebar({ onNavigate }) {
  const { user, isAuth, logout } = useAuth();
  const location = useLocation();

  const isActive = (to) => {
    if (to === '/') return location.pathname === '/';
    return location.pathname.startsWith(to);
  };

  const nav = (to, label) => {
    const active = isActive(to);
    return (
      <Link
        to={to}
        onClick={onNavigate}
        aria-current={active ? 'page' : undefined}
        className={`block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          active
            ? 'bg-accent/15 text-accent-light'
            : 'text-text-secondary hover:text-text hover:bg-surface-2'
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <aside className="w-60 h-full bg-bg border-r border-border p-4 flex flex-col overflow-y-auto" aria-label="Main navigation">
      <Link to="/" onClick={onNavigate} className="mb-6 block" aria-label="BingeFinder home">
        <span className="text-lg font-bold tracking-tight text-text" style={{ fontFamily: 'Sora, sans-serif' }}>
          Binge<span className="text-accent">Finder</span>
        </span>
        <span className="block text-[10px] uppercase tracking-[0.14em] text-text-muted mt-0.5">
          {t('hero.tagline')}
        </span>
      </Link>

      <NavGroup label={t('nav.discoverGroup')}>
        {nav('/', t('nav.home'))}
        {nav('/series', t('nav.series'))}
        {nav('/anime', t('nav.anime'))}
        {nav('/discover', t('nav.discover'))}
      </NavGroup>

      <Link
        to="/surprise"
        onClick={onNavigate}
        aria-current={isActive('/surprise') ? 'page' : undefined}
        className={`mb-5 flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-bold text-bg transition-all duration-200 ${
          isActive('/surprise')
            ? 'bg-accent-light shadow-[0_8px_24px_-8px_rgba(91,157,255,0.8)]'
            : 'bg-gradient-to-r from-accent to-accent-light hover:brightness-110 hover:shadow-[0_8px_24px_-8px_rgba(91,157,255,0.7)]'
        }`}
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 2l1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9L12 2zm7 12l.9 2.6L22.5 17.5l-2.6.9L19 21l-.9-2.6-2.6-.9 2.6-.9L19 14zM5 15l.7 2.1L7.8 18l-2.1.7L5 21l-.7-2.3L2.2 18l2.1-.9L5 15z" />
        </svg>
        {t('nav.surprise')}
      </Link>

      {isAuth && (
        <NavGroup label={t('nav.libraryGroup')}>
          {nav('/for-you', t('nav.forYou'))}
          {nav('/watchlist', t('nav.watchlist'))}
          {nav('/liked', t('nav.liked'))}
          {nav('/recently-viewed', t('nav.recentlyViewed'))}
        </NavGroup>
      )}

      <div className="mt-auto pt-4 border-t border-border">
        {isAuth ? (
          <div className="flex items-center justify-between gap-2 mt-2">
            <span className="text-sm text-text-secondary truncate min-w-0">{user?.name}</span>
            <button
              onClick={() => { logout(); onNavigate?.(); }}
              className="text-xs text-text-muted hover:text-danger transition-colors flex-shrink-0"
            >
              {t('auth.logout')}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-2 mt-2">
            <Link to="/login" onClick={onNavigate} className="btn-ghost text-xs text-center">
              {t('auth.login')}
            </Link>
            <Link to="/signup" onClick={onNavigate} className="btn-primary text-xs text-center">
              {t('auth.signup')}
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}
