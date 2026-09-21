import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { notificationsApi } from '../api/notifications';
import { Shield, Bell, User, LogOut, Radio, MapPin, Sparkles } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, logout, demoLogin } = useAuth();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState<number>(0);

  useEffect(() => {
    if (user) {
      notificationsApi.getNotifications()
        .then((items) => {
          const count = items.filter((n) => !n.is_read).length;
          setUnreadCount(count);
        })
        .catch(() => {});
    }
  }, [user]);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <header className="navbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <Link to="/" className="brand-logo">
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 15px rgba(59, 130, 246, 0.4)',
            }}
          >
            <Shield size={22} color="#ffffff" />
          </div>
          <span>Voxentra<span style={{ color: '#3b82f6' }}>AI</span></span>
          <span className="brand-badge" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#93c5fd', borderColor: 'rgba(59, 130, 246, 0.4)' }}>
            DISPATCH HQ
          </span>
        </Link>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        {/* Live Inbound Call & AI Dispatcher link */}
        <Link
          to="/"
          className="btn btn-sm"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.25))',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            color: '#34d399',
            fontWeight: 700,
          }}
        >
          <Radio size={14} className="animate-pulse" />
          <span>📞 1913 Telephony Dispatch</span>
        </Link>

        {/* Live GIS Map */}
        <Link
          to="/map"
          className="btn btn-secondary btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <MapPin size={14} />
          <span>GIS Incident Map</span>
        </Link>

        {/* Admin or Officer Quick Portal */}
        {user ? (
          <>
            {user.role === 'ADMIN' && (
              <Link
                to="/admin"
                className="btn btn-primary btn-sm"
                style={{ fontWeight: 700 }}
              >
                <span>👑 Admin Command</span>
              </Link>
            )}
            {user.role === 'OFFICER' && (
              <Link
                to="/officer"
                className="btn btn-primary btn-sm"
                style={{ fontWeight: 700 }}
              >
                <span>🛡️ Officer Queue</span>
              </Link>
            )}

            <Link
              to="/notifications"
              className="btn btn-secondary btn-sm"
              style={{ position: 'relative', padding: '0.5rem' }}
              title="Notifications"
            >
              <Bell size={16} />
              {unreadCount > 0 && (
                <span
                  style={{
                    position: 'absolute',
                    top: '-4px',
                    right: '-4px',
                    background: '#ef4444',
                    color: '#ffffff',
                    borderRadius: '50%',
                    width: '18px',
                    height: '18px',
                    fontSize: '0.7rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                  }}
                >
                  {unreadCount}
                </span>
              )}
            </Link>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginLeft: '0.5rem' }}>
              <Link
                to="/profile"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  textDecoration: 'none',
                  color: 'var(--text-light)',
                  background: 'rgba(255, 255, 255, 0.05)',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-full)',
                  border: '1px solid var(--border-color)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                }}
              >
                <User size={15} color="#38bdf8" />
                <span>{user.full_name}</span>
                <span style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.2)', color: '#93c5fd' }}>
                  {user.role}
                </span>
              </Link>

              <button
                onClick={handleLogout}
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.5rem', color: '#f87171' }}
                title="Logout"
              >
                <LogOut size={16} />
              </button>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              onClick={() => demoLogin('ADMIN').then(() => navigate('/admin'))}
              className="btn btn-primary btn-sm"
              style={{ fontWeight: 700 }}
            >
              <span>👑 Admin Login</span>
            </button>
            <button
              onClick={() => demoLogin('OFFICER_WATER').then(() => navigate('/officer'))}
              className="btn btn-secondary btn-sm"
              style={{ fontWeight: 700 }}
            >
              <span>💧 Officer Login</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
