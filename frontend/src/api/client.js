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

  // A 401 during an authenticated request means a stale/expired session.
  // Skip the redirect for the auth endpoints themselves (a failed login with
  // the wrong password is a normal 401, not a session-expiry signal).
  const isAuthEndpoint = path.startsWith('/auth/');
  if (res.status === 401 && !isAuthEndpoint) {
    localStorage.removeItem('bf_token');
    window.location.href = '/login';
    throw new Error('Session expired. Please log in again.');
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      const raw = body.detail ?? body.message;
      if (Array.isArray(raw)) {
        // FastAPI validation errors carry {type, loc, msg} entries. Surface
        // the human-readable messages joined together, not the raw array
        // (which stringifies to "[object Object]").
        const parts = raw.map(e => e.msg || String(e)).filter(Boolean);
        detail = parts.length ? parts.join(' ') : res.statusText;
      } else if (raw != null) {
        detail = typeof raw === 'string' ? raw : JSON.stringify(raw);
      }
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

  regions: () => request('/regions'),
  resolveRegion: (code) => request(`/regions/${code}`),

  tonightsBinge: (contentType) => {
    const qs = contentType ? `?content_type=${encodeURIComponent(contentType)}` : '';
    return request(`/discover/tonights-binge${qs}`);
  },
  trending: (contentType) => {
    const qs = contentType ? `?content_type=${encodeURIComponent(contentType)}` : '';
    return request(`/discover/trending${qs}`);
  },
  newNoteworthy: (contentType) => {
    const qs = contentType ? `?content_type=${encodeURIComponent(contentType)}` : '';
    return request(`/discover/new-noteworthy${qs}`);
  },
  hiddenGems: (contentType) => {
    const qs = contentType ? `?content_type=${encodeURIComponent(contentType)}` : '';
    return request(`/discover/hidden-gems${qs}`);
  },
  freeTonight: (region, contentType) => {
    const params = new URLSearchParams();
    if (region) params.set('region', region);
    if (contentType) params.set('content_type', contentType);
    const qs = params.toString();
    return request(`/discover/free-tonight${qs ? `?${qs}` : ''}`);
  },
  surprise: () => request('/discover/surprise'),
  vibes: () => request('/discover/vibes'),
  vibeFiltered: (key) => request(`/discover/vibes/${key}`),

  seriesRecs: (id) => request(`/series/${id}/recommendations`),
  personalizedRecs: (region) => {
    const qs = region ? `?region=${encodeURIComponent(region)}` : '';
    return request(`/recommendations/personalized${qs}`);
  },

  watchProviders: (id, region) => {
    const qs = region ? `?region=${encodeURIComponent(region)}` : '';
    return request(`/series/${id}/watch-providers${qs}`);
  },
  availableProviders: (region) => {
    const qs = region ? `?region=${encodeURIComponent(region)}` : '';
    return request(`/watch-providers/available${qs}`);
  },

  watchlist: () => request('/user/watchlist'),
  addWatchlist: (id) => request(`/user/watchlist/${id}`, { method: 'POST' }),
  removeWatchlist: (id) => request(`/user/watchlist/${id}`, { method: 'DELETE' }),
  likes: () => request('/user/likes'),
  like: (id) => request(`/user/likes/${id}`, { method: 'POST' }),
  unlike: (id) => request(`/user/likes/${id}`, { method: 'DELETE' }),
  reactions: () => request('/user/reactions'),
  setReaction: (id, reaction) =>
    request(`/user/reactions/${id}?reaction=${encodeURIComponent(reaction)}`, { method: 'POST' }),
  clearReaction: (id) => request(`/user/reactions/${id}`, { method: 'DELETE' }),
  recentlyViewed: () => request('/user/recently-viewed'),
  recordView: (id) => request(`/user/recently-viewed/${id}`, { method: 'POST' }),

  getSettings: () => request('/user/settings'),
  updateSettings: (data) => request('/user/settings', { method: 'PUT', body: JSON.stringify(data) }),

  // Events (adaptive ranking feedback)
  recordEvent: (data) => request('/events/recommendation', { method: 'POST', body: JSON.stringify(data) }),
  adaptiveStatus: () => request('/events/status'),
};
