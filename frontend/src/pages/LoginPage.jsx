import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto mt-16">
      <h1 className="text-xl font-bold text-text mb-1 text-center">Welcome back</h1>
      <p className="text-sm text-text-muted text-center mb-6">Log in to your account</p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger text-center">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="login-email" className="block text-sm font-medium text-text-secondary mb-1">Email</label>
          <input id="login-email" type="email" value={email} onChange={e => setEmail(e.target.value)}
                 placeholder="you@example.com" required autoComplete="email"
                 className="w-full px-3 py-2.5 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent" />
        </div>
        <div>
          <label htmlFor="login-password" className="block text-sm font-medium text-text-secondary mb-1">Password</label>
          <div className="relative">
            <input id="login-password" type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                   placeholder="Enter your password" required autoComplete="current-password"
                   className="w-full px-3 py-2.5 pr-12 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent" />
            <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-muted hover:text-text-secondary">
              {showPw ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>
        <button type="submit" disabled={loading}
                className="btn-primary w-full" disabled={loading}>
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <p className="text-center text-sm text-text-muted mt-6">
        Don't have an account? <Link to="/signup" className="text-accent hover:underline">Sign up</Link>
      </p>
    </div>
  );
}
