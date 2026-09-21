import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Radio,
  MapPin,
  History,
  ShieldCheck,
  Building2,
  Users,
  Bell,
  User,
  Sparkles,
  PhoneCall
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { user } = useAuth();

  if (!user) return null;

  const linkStyle = ({ isActive }: { isActive: boolean }) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    padding: '0.75rem 1rem',
    borderRadius: 'var(--radius-md)',
    color: isActive ? '#ffffff' : 'var(--text-muted)',
    background: isActive ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(37, 99, 235, 0.15))' : 'transparent',
    border: isActive ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid transparent',
    textDecoration: 'none',
    fontWeight: isActive ? 600 : 500,
    fontSize: '0.9rem',
    transition: 'all 0.2s ease',
  });

  return (
    <aside
      style={{
        width: '250px',
        background: 'rgba(15, 23, 42, 0.65)',
        borderRight: '1px solid var(--border-color)',
        padding: '1.5rem 1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        flexShrink: 0,
      }}
    >
      <div style={{ padding: '0.5rem 1rem', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {user.role} OPERATIONS
        </span>
      </div>

      {user.role === 'ADMIN' && (
        <>
          <NavLink to="/admin" style={linkStyle}>
            <ShieldCheck size={18} color="#60a5fa" />
            <span>Admin Command Hub</span>
          </NavLink>

          <NavLink to="/officer" style={linkStyle}>
            <LayoutDashboard size={18} />
            <span>Department Queues</span>
          </NavLink>

          <NavLink to="/map" style={linkStyle}>
            <MapPin size={18} color="#34d399" />
            <span>GIS Heatmap</span>
          </NavLink>

          <NavLink to="/history" style={linkStyle}>
            <History size={18} />
            <span>Telephony Records</span>
          </NavLink>
        </>
      )}

      {user.role === 'OFFICER' && (
        <>
          <NavLink to="/officer" style={linkStyle}>
            <LayoutDashboard size={18} color="#60a5fa" />
            <span>Assigned Dept Queue</span>
          </NavLink>

          <NavLink to="/map" style={linkStyle}>
            <MapPin size={18} color="#34d399" />
            <span>Field Map GIS</span>
          </NavLink>

          <NavLink to="/history" style={linkStyle}>
            <History size={18} />
            <span>Resolution Archive</span>
          </NavLink>
        </>
      )}

      {user.role === 'CITIZEN' && (
        <>
          <NavLink to="/dashboard" style={linkStyle}>
            <LayoutDashboard size={18} />
            <span>Citizen Dashboard</span>
          </NavLink>
          <NavLink to="/history" style={linkStyle}>
            <History size={18} />
            <span>My Complaints</span>
          </NavLink>
        </>
      )}

      <div style={{ height: '1px', background: 'var(--border-color)', margin: '0.75rem 0' }} />

      <div style={{ padding: '0.25rem 1rem', marginBottom: '0.25rem' }}>
        <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>
          Telephony Services
        </span>
      </div>

      <NavLink to="/" style={linkStyle}>
        <Radio size={18} color="#4ade80" />
        <span style={{ color: '#4ade80', fontWeight: 600 }}>1913 AI Call Dispatch</span>
      </NavLink>

      <NavLink to="/toll-free" style={linkStyle}>
        <PhoneCall size={18} color="#38bdf8" />
        <span>Full IVR Simulator</span>
      </NavLink>

      <NavLink to="/notifications" style={linkStyle}>
        <Bell size={18} />
        <span>System Alerts</span>
      </NavLink>

      <NavLink to="/profile" style={linkStyle}>
        <User size={18} />
        <span>My Staff Profile</span>
      </NavLink>
    </aside>
  );
};
