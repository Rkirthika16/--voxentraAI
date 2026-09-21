import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import { User as UserIcon, Mail, Phone, Shield, LogOut, Save, CheckCircle2, Calendar } from 'lucide-react';
import { ErrorMessage } from '../components/ErrorMessage';

export const ProfilePage: React.FC = () => {
  const { user, refreshUser, logout } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(false);

    try {
      await authApi.updateProfile({ full_name: fullName, phone });
      await refreshUser();
      setSuccessMsg(true);
      setTimeout(() => setSuccessMsg(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update profile.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const joinedDate = new Date(user.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div className="page-container animate-fade-in" style={{ maxWidth: '650px', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div>
        <h1 style={{ fontSize: '1.85rem', marginBottom: '0.35rem' }}>User Profile</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          Manage your account settings and contact information
        </p>
      </div>

      <div className="glass-card" style={{ padding: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1.5rem' }}>
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontSize: '1.5rem',
              fontWeight: 700,
            }}
          >
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 style={{ fontSize: '1.35rem', marginBottom: '0.25rem' }}>{user.full_name}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa' }}>
                <Shield size={12} /> {user.role}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Calendar size={12} /> Registered: {joinedDate}
              </span>
            </div>
          </div>
        </div>

        {successMsg && (
          <div
            style={{
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '0.75rem 1rem',
              marginBottom: '1.5rem',
              color: '#34d399',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <CheckCircle2 size={16} />
            <span>Profile updated successfully!</span>
          </div>
        )}

        {error && <ErrorMessage message={error} />}

        <form onSubmit={handleUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="prof-name">Full Name</label>
            <div style={{ position: 'relative' }}>
              <input
                id="prof-name"
                type="text"
                required
                className="form-input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <UserIcon size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="prof-email">Email Address (Non-editable)</label>
            <div style={{ position: 'relative' }}>
              <input
                id="prof-email"
                type="email"
                disabled
                className="form-input"
                value={user.email}
                style={{ paddingLeft: '2.5rem', opacity: 0.6, cursor: 'not-allowed' }}
              />
              <Mail size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" htmlFor="prof-phone">Contact Phone Number</label>
            <div style={{ position: 'relative' }}>
              <input
                id="prof-phone"
                type="tel"
                className="form-input"
                placeholder="e.g. 9843000000"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <Phone size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
            <button type="button" onClick={handleLogout} className="btn btn-danger btn-sm">
              <LogOut size={15} /> Logout
            </button>

            <button type="submit" className="btn btn-primary btn-sm" disabled={isSaving}>
              <Save size={15} /> {isSaving ? 'Saving...' : 'Save Profile Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
