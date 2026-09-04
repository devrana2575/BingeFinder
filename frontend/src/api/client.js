const API_BASE = '/api';

async function request(path, options = {}) {
  const token = localStorage.getItem('bf_token');
  const headers = { ...options.headers };

  const hasBody = options.body != null;
  if (hasBody && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('bf_token');
    window.location.href = '/login';
    throw new Error('Session expired. Please log in again.');
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {}
    throw new Error(detail);
  }

  return res.json();
}

export const api = {
  signup: (data) => request('/auth/signup', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),

  catalogCount: () => request('/series/count'),
  search: (params) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, v); });
    return request(`/series/search?${qs.toString()}`);
  },
  filterOptions: () => request('/series/filters'),
  getSeries: (id) => request(`/series/${id}`),

  tonightsBinge: () => request('/discover/tonights-binge'),
  hiddenGems: () => request('/discover/hidden-gems'),
  freeTonight: () => request('/discover/free-tonight'),
  surprise: () => request('/discover/surprise'),
  vibes: () => request('/discover/vibes'),
  vibeFiltered: (key) => request(`/discover/vibes/${key}`),

  seriesRecs: (id) => request(`/series/${id}/recommendations`),
  personalizedRecs: () => request('/recommendations/personalized'),

  watchProviders: (id) => request(`/series/${id}/watch-providers`),

  watchlist: () => request('/user/watchlist'),
  addWatchlist: (id) => request(`/user/watchlist/${id}`, { method: 'POST' }),
  removeWatchlist: (id) => request(`/user/watchlist/${id}`, { method: 'DELETE' }),
  likes: () => request('/user/likes'),
  like: (id) => request(`/user/likes/${id}`, { method: 'POST' }),
  unlike: (id) => request(`/user/likes/${id}`, { method: 'DELETE' }),
  recentlyViewed: () => request('/user/recently-viewed'),
  recordView: (id) => request(`/user/recently-viewed/${id}`, { method: 'POST' }),

  // Events (adaptive ranking feedback)
  recordEvent: (data) => request('/events/recommendation', { method: 'POST', body: JSON.stringify(data) }),
  adaptiveStatus: () => request('/events/status'),
};
