/**
 * Resolve the post-login destination from router state.
 *
 * Only same-origin, internal paths are accepted so a malformed or forged
 * history state can never turn the login page into an open redirect.
 */
export function getReturnPath(from, fallback = '/') {
  if (!from || typeof from.pathname !== 'string') return fallback;
  if (!from.pathname.startsWith('/') || from.pathname.startsWith('//')) return fallback;
  if (from.pathname === '/login' || from.pathname === '/signup') return fallback;
  return `${from.pathname}${from.search || ''}${from.hash || ''}`;
}
