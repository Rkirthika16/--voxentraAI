import React, { useState, useEffect } from 'react';
import { adminApi } from '../api/admin';
import { complaintsApi } from '../api/complaints';
import { AdminStats, Department, User, Complaint } from '../types';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { LiveComplaintMap } from '../components/LiveComplaintMap';
import {
  ShieldCheck,
  Building2,
  Users,
  AlertTriangle,
  CheckCircle2,
  Clock,
  TrendingUp,
  Plus,
  RefreshCw,
  Activity,
  MapPin
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [officers, setOfficers] = useState<User[]>([]);
  const [mapComplaints, setMapComplaints] = useState<Complaint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Officer Modal State
  const [showOfficerModal, setShowOfficerModal] = useState(false);
  const [newOfficerName, setNewOfficerName] = useState('');
  const [newOfficerEmail, setNewOfficerEmail] = useState('');
  const [newOfficerPhone, setNewOfficerPhone] = useState('');
  const [newOfficerPass, setNewOfficerPass] = useState('');
  const [newOfficerDeptId, setNewOfficerDeptId] = useState<number | ''>('');
  const [isCreatingOfficer, setIsCreatingOfficer] = useState(false);

  const fetchAdminData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, deptsData, officersData, mapData] = await Promise.all([
        adminApi.getStats(),
        adminApi.listDepartments(),
        adminApi.listUsers('OFFICER'),
        complaintsApi.getMapPins({ limit: 100 }).catch(() => [])
      ]);
      setStats(statsData);
      setDepartments(deptsData);
      setOfficers(officersData);
      setMapComplaints(mapData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load administrator dashboard.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleCreateOfficer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOfficerDeptId) return;

    setIsCreatingOfficer(true);
    try {
      await adminApi.createOfficer({
        full_name: newOfficerName,
        email: newOfficerEmail,
        password: newOfficerPass,
        phone: newOfficerPhone || undefined,
        department_id: Number(newOfficerDeptId),
      });

      setShowOfficerModal(false);
      setNewOfficerName('');
      setNewOfficerEmail('');
      setNewOfficerPhone('');
      setNewOfficerPass('');
      setNewOfficerDeptId('');
      await fetchAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create officer account.');
    } finally {
      setIsCreatingOfficer(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Calculating real municipal database metrics..." />;
  }

  if (error || !stats) {
    return (
      <div className="page-container">
        <ErrorMessage message={error || 'Failed to load statistics.'} onRetry={fetchAdminData} />
      </div>
    );
  }

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.85rem', marginBottom: '0.35rem' }}>Municipal Administration Analytics</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Live aggregated metrics and operations management across Tamil Nadu civic departments
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={() => setShowOfficerModal(true)} className="btn btn-primary btn-sm">
            <Plus size={15} /> Add Department Officer
          </button>
          <button onClick={fetchAdminData} className="btn btn-secondary btn-sm">
            <RefreshCw size={15} /> Refresh Data
          </button>
        </div>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid-4">
        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Complaints</span>
            <Activity size={18} color="#60a5fa" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800 }}>{stats.total_complaints}</div>
          <span style={{ fontSize: '0.75rem', color: '#34d399' }}>Live Database Count</span>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>In Progress</span>
            <Clock size={18} color="#fbbf24" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800 }}>{stats.in_progress}</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Active Field Work</span>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Resolved</span>
            <CheckCircle2 size={18} color="#34d399" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800 }}>{stats.resolved}</div>
          <span style={{ fontSize: '0.75rem', color: '#34d399' }}>Completed Grievances</span>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Emergency Critical</span>
            <AlertTriangle size={18} color="#f87171" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#f87171' }}>{stats.emergency_critical}</div>
          <span style={{ fontSize: '0.75rem', color: '#f87171' }}>Urgent Action Flagged</span>
        </div>
      </div>

      {/* Live Map Geographic Hotspots Overview */}
      <div className="glass-card" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MapPin size={20} color="#38bdf8" /> Live Tamil Nadu Regional Hotspots & Geolocation GIS
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: '0.25rem 0 0 0' }}>
              Interactive real-time map of complaints received via Toll-Free 1913, Voice, and Web portals
            </p>
          </div>
          <span style={{ fontSize: '0.8rem', color: '#60a5fa', background: 'rgba(59, 130, 246, 0.15)', padding: '0.3rem 0.75rem', borderRadius: 'var(--radius-full)', fontWeight: 600 }}>
            {mapComplaints.length} Geocoded Grievances Active
          </span>
        </div>

        <LiveComplaintMap
          complaints={mapComplaints}
          height="450px"
          showFilters={true}
        />
      </div>

      {/* Department Breakdown Table */}
      <div className="glass-card" style={{ padding: '1.75rem' }}>
        <h3 style={{ fontSize: '1.2rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Building2 size={20} color="#a78bfa" /> Department Workload & Resolution Metrics
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-dim)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Department Name</th>
                <th style={{ padding: '0.75rem 1rem' }}>Total Received</th>
                <th style={{ padding: '0.75rem 1rem' }}>Pending</th>
                <th style={{ padding: '0.75rem 1rem' }}>In Progress</th>
                <th style={{ padding: '0.75rem 1rem' }}>Resolved</th>
              </tr>
            </thead>
            <tbody>
              {stats.departments.map((dept) => (
                <tr key={dept.department_id} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                  <td style={{ padding: '0.85rem 1rem', fontWeight: 600, color: 'var(--text-main)' }}>
                    {dept.department_name}
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}>{dept.total}</td>
                  <td style={{ padding: '0.85rem 1rem', color: '#a78bfa' }}>{dept.pending}</td>
                  <td style={{ padding: '0.85rem 1rem', color: '#fbbf24' }}>{dept.in_progress}</td>
                  <td style={{ padding: '0.85rem 1rem', color: '#34d399', fontWeight: 600 }}>{dept.resolved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Category & Officer Management Grid */}
      <div className="grid-2">
        {/* Category Breakdown */}
        <div className="glass-card" style={{ padding: '1.75rem' }}>
          <h3 style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>Category Distribution</h3>
          {stats.categories.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>No categorized complaints recorded yet.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {stats.categories.map((c) => (
                <div key={c.category} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-input)', padding: '0.65rem 1rem', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ fontWeight: 600 }}>{c.category}</span>
                  <span style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', padding: '0.15rem 0.6rem', borderRadius: 'var(--radius-full)', fontSize: '0.8rem', fontWeight: 700 }}>
                    {c.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Officers Directory */}
        <div className="glass-card" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Users size={18} color="#34d399" /> Registered Department Officers
            </h3>
          </div>
          {officers.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>No officers registered.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', maxHeight: '280px', overflowY: 'auto' }}>
              {officers.map((off) => (
                <div key={off.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-input)', padding: '0.65rem 1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{off.full_name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{off.email}</div>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: '#a78bfa', background: 'rgba(139, 92, 246, 0.15)', padding: '0.2rem 0.5rem', borderRadius: 'var(--radius-sm)' }}>
                    Officer
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Officer Modal */}
      {showOfficerModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
        >
          <div className="glass-card animate-fade-in" style={{ maxWidth: '500px', width: '100%', padding: '2rem' }}>
            <h3 style={{ fontSize: '1.3rem', marginBottom: '0.5rem' }}>Add Department Officer</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
              Create an official account to manage department grievances
            </p>

            <form onSubmit={handleCreateOfficer} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Full Name *</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  placeholder="e.g. Officer Ramanathan"
                  value={newOfficerName}
                  onChange={(e) => setNewOfficerName(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Official Email Address *</label>
                <input
                  type="email"
                  required
                  className="form-input"
                  placeholder="officer.dept@voxentra.tn.gov.in"
                  value={newOfficerEmail}
                  onChange={(e) => setNewOfficerEmail(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Department *</label>
                <select
                  className="form-select"
                  required
                  value={newOfficerDeptId}
                  onChange={(e) => setNewOfficerDeptId(e.target.value ? Number(e.target.value) : '')}
                >
                  <option value="">-- Assign Department --</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Phone Number</label>
                <input
                  type="tel"
                  className="form-input"
                  placeholder="9843000000"
                  value={newOfficerPhone}
                  onChange={(e) => setNewOfficerPhone(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Temporary Password *</label>
                <input
                  type="password"
                  required
                  className="form-input"
                  placeholder="Min 6 characters"
                  value={newOfficerPass}
                  onChange={(e) => setNewOfficerPass(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowOfficerModal(false)}
                  className="btn btn-secondary btn-sm"
                  disabled={isCreatingOfficer}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={isCreatingOfficer}
                >
                  {isCreatingOfficer ? 'Creating...' : 'Create Officer Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
