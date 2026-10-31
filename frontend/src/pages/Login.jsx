import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { useAuth } from '../auth/AuthContext.jsx';
import { errorMessage, fieldErrors } from '../api/client.js';

export default function Login() {
  const { login, register, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState({});

  if (isAuthenticated) return <Navigate to={location.state?.from?.pathname || '/'} replace />;

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setErrors({});
    try {
      if (mode === 'login') await login({ username: form.username, password: form.password });
      else await register(form);
      navigate(location.state?.from?.pathname || '/', { replace: true });
    } catch (err) {
      setErrors(fieldErrors(err));
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit}>
        <div className="brand brand-dark">
          <Activity size={24} aria-hidden="true" />
          <span>TrustRoute</span>
        </div>
        <h1>{mode === 'login' ? 'Sign in' : 'Create your account'}</h1>
        <p className="muted">API monitoring &amp; reliability analysis</p>
        {error && (
          <div className="notice notice-error" role="alert">
            {error}
          </div>
        )}
        <div className="field">
          <label htmlFor="username">Username</label>
          <input id="username" autoComplete="username" required value={form.username} onChange={set('username')} aria-invalid={Boolean(errors.username)} />
        </div>
        {mode === 'register' && (
          <div className="field">
            <label htmlFor="email">Email (optional, used for email alerts)</label>
            <input id="email" type="email" autoComplete="email" value={form.email} onChange={set('email')} />
          </div>
        )}
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
            value={form.password}
            onChange={set('password')}
            aria-invalid={Boolean(errors.password)}
          />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
        <button
          type="button"
          className="link-btn"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError('');
            setErrors({});
          }}
        >
          {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  );
}
