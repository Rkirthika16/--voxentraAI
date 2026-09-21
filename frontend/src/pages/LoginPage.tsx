import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock, Mail, ArrowRight, Zap, AlertCircle } from 'lucide-react';
import { LoadingSpinner } from '../components/LoadingSpinner';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, demoLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectUser = (role: string) => {
    const from = (location.state as any)?.from?.pathname;
    if (from) {
      navigate(from, { replace: true });
      return;
    }
    if (role === 'ADMIN') navigate('/admin');
    else if (role === 'OFFICER') navigate('/officer');
    else navigate('/dashboard');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const res = await login(email, password);
      redirectUser(res.role);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Invalid email or password. Please try again.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDemo = async (role: 'CITIZEN' | 'OFFICER_WATER' | 'OFFICER_ROADS' | 'ADMIN') => {
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await demoLogin(role);
      redirectUser(res.role);
    } catch (err: any) {
      setError('Demo login failed. Please ensure the backend is running.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '520px', padding: '3rem 1rem' }}>
      <div className="glass-card animate-fade-in" style={{ padding: '2.5rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1rem',
            }}
          >
            <Shield size={28} color="#ffffff" />
          </div>
          <h2 style={{ fontSize: '1.75rem', marginBottom: '0.4rem' }}>Portal Login</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Access Citizen, Officer, or Admin municipal services
          </p>
        </div>

        {error && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '0.75rem 1rem',
              marginBottom: '1.5rem',
              color: '#fca5a5',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <AlertCircle size={16} color="#ef4444" style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="email">Email Address</label>
            <div style={{ position: 'relative' }}>
              <input
                id="email"
                type="email"
                required
                className="form-input"
                placeholder="name@voxentra.tn.gov.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <Mail size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                type="password"
                required
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <Lock size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '0.5rem' }}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Signing in...' : 'Sign In'} <ArrowRight size={16} />
          </button>
        </form>

        {/* Quick Demo Access Bar */}
        <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#fbbf24', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.75rem', justifyContent: 'center' }}>
            <Zap size={14} /> Quick 1-Click Demo Logins
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem' }}>
            <button type="button" onClick={() => handleDemo('CITIZEN')} className="btn btn-secondary btn-sm">
              Citizen Demo
            </button>
            <button type="button" onClick={() => handleDemo('OFFICER_WATER')} className="btn btn-secondary btn-sm">
              Water Officer
            </button>
            <button type="button" onClick={() => handleDemo('OFFICER_ROADS')} className="btn btn-secondary btn-sm">
              Roads Officer
            </button>
            <button type="button" onClick={() => handleDemo('ADMIN')} className="btn btn-secondary btn-sm">
              Admin Demo
            </button>
          </div>
        </div>

        <p style={{ textAlign: 'center', marginTop: '1.75rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          New citizen? <Link to="/register" style={{ color: 'var(--color-primary)', fontWeight: 600 }}>Create an account</Link>
        </p>
      </div>
    </div>
  );
};
