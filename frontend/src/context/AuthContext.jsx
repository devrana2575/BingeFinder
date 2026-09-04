import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('bf_token');
    if (!token) { setLoading(false); return; }
    api.me()
      .then(u => setUser(u))
      .catch(() => localStorage.removeItem('bf_token'))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.login({ email, password });
    localStorage.setItem('bf_token', res.access_token);
    setUser(res.user);
    return res;
  }, []);

  const signup = useCallback(async (name, email, password) => {
    const res = await api.signup({ name, email, password });
    localStorage.setItem('bf_token', res.access_token);
    setUser(res.user);
    return res;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('bf_token');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, isAuth: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
