import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

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
          BingeFinder
        </span>
      </Link>

      <nav className="flex flex-col gap-0.5" aria-label="Main navigation">
        {nav('/', 'Home')}
        {nav('/discover', 'Discover')}
        {nav('/surprise', 'Surprise Me')}
      </nav>

      {isAuth && (
        <>
          <div className="border-t border-border my-4" />
          <nav className="flex flex-col gap-0.5" aria-label="User navigation">
            {nav('/for-you', 'For You', true)}
            {nav('/watchlist', 'Watchlist', true)}
            {nav('/liked', 'Liked', true)}
            {nav('/recently-viewed', 'Recently Viewed', true)}
          </nav>
        </>
      )}

      <div className="mt-auto pt-4 border-t border-border">
        {isAuth ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-text-secondary truncate min-w-0">{user?.name}</span>
            <button
              onClick={() => { logout(); onNavigate?.(); }}
              className="text-xs text-text-muted hover:text-danger transition-colors flex-shrink-0"
            >
              Logout
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <Link to="/login" onClick={onNavigate} className="btn-ghost text-xs text-center">
              Log In
            </Link>
            <Link to="/signup" onClick={onNavigate} className="btn-primary text-xs text-center">
              Sign Up
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}
