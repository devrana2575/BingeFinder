import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import RegionSelector from './RegionSelector';
import { t } from '../i18n';

export default function Sidebar({ onNavigate }) {
  const { user, isAuth, logout } = useAuth();
  const location = useLocation();

  const isActive = (to) => {
    if (to === '/') return location.pathname === '/';
    return location.pathname.startsWith(to);
  };

  const nav = (to, label, needsAuth = false) => {
    if (needsAuth && !isAuth) return null;
    const active = isActive(to);
    return (
      <Link
        to={to}
        onClick={onNavigate}
        className={`block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          active
            ? 'bg-accent/10 text-accent'
            : 'text-text-secondary hover:text-text hover:bg-surface-2'
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <aside className="w-60 h-screen bg-surface border-r border-border p-4 flex flex-col sticky top-0">
      <Link to="/" onClick={onNavigate} className="mb-6">
        <span className="text-lg font-bold text-text" style={{ fontFamily: 'Sora, sans-serif' }}>
          {t('brand.name')}
        </span>
      </Link>

      <nav className="flex flex-col gap-0.5" aria-label="Primary navigation">
        {nav('/', t('nav.home'))}
        {nav('/discover', t('nav.discover'))}
        {nav('/surprise', t('nav.surprise'))}
        {nav('/settings', t('nav.settings'))}
      </nav>

      {isAuth && (
        <>
          <div className="border-t border-border my-4" />
          <nav className="flex flex-col gap-0.5" aria-label="Account navigation">
            {nav('/for-you', t('nav.forYou'), true)}
            {nav('/watchlist', t('nav.watchlist'), true)}
            {nav('/liked', t('nav.liked'), true)}
            {nav('/recently-viewed', t('nav.recentlyViewed'), true)}
          </nav>
        </>
      )}

      <div className="mt-auto pt-4 border-t border-border">
        <RegionSelector />
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