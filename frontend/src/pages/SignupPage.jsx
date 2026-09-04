import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      await signup(name, email, password);
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto mt-16">
      <h1 className="text-xl font-bold text-text mb-1 text-center">Create an account</h1>
      <p className="text-sm text-text-muted text-center mb-6">Start finding your next binge</p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger text-center">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="signup-name" className="block text-sm font-medium text-text-secondary mb-1">Name</label>
          <input id="signup-name" type="text" value={name} onChange={e => setName(e.target.value)}
                 placeholder="Your name" required autoComplete="name"
                 className="w-full px-3 py-2.5 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent" />
        </div>
        <div>
          <label htmlFor="signup-email" className="block text-sm font-medium text-text-secondary mb-1">Email</label>
          <input id="signup-email" type="email" value={email} onChange={e => setEmail(e.target.value)}
                 placeholder="you@example.com" required autoComplete="email"
                 className="w-full px-3 py-2.5 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent" />
        </div>
        <div>
          <label htmlFor="signup-password" className="block text-sm font-medium text-text-secondary mb-1">Password</label>
          <div className="relative">
            <input id="signup-password" type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                   placeholder="Min 6 characters" required minLength={6} autoComplete="new-password"
                   className="w-full px-3 py-2.5 pr-12 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent" />
            <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-muted hover:text-text-secondary">
              {showPw ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>
        <div>
          <label htmlFor="signup-confirm" className="block text-sm font-medium text-text-secondary mb-1">Confirm Password</label>
          <input id="signup-confirm" type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                 placeholder="Repeat your password" required minLength={6} autoComplete="new-password"
                 className="w-full px-3 py-2.5 rounded-lg bg-surface border border-border text-text text-sm placeholder:text-text-muted focus:border-accent" />
        </div>
        <button type="submit" disabled={loading}
                className="btn-primary w-full">
          {loading ? 'Creating account...' : 'Create Account'}
        </button>
      </form>

      <p className="text-center text-sm text-text-muted mt-6">
        Already have an account? <Link to="/login" className="text-accent hover:underline">Log in</Link>
      </p>
    </div>
  );
}
