import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { officersApi } from '../api/officers';
import { Complaint } from '../types';
import { ComplaintCard } from '../components/ComplaintCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import {
  Shield,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ListFilter
} from 'lucide-react';

export const OfficerDashboard: React.FC = () => {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [assignedOnly, setAssignedOnly] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQueue = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await officersApi.getAssignedComplaints(assignedOnly);
      setComplaints(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load officer queue.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [assignedOnly]);

  const total = complaints.length;
  const inProgress = complaints.filter((c) => c.status === 'IN_PROGRESS').length;
  const critical = complaints.filter((c) => c.priority === 'CRITICAL').length;
  const resolved = complaints.filter((c) => c.status === 'RESOLVED').length;

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Welcome Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.85rem', marginBottom: '0.35rem' }}>
            Officer Dispatch Queue — {user?.full_name}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Department Investigation & SLA Management Workspace
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => setAssignedOnly(!assignedOnly)}
            className="btn btn-secondary btn-sm"
          >
            <ListFilter size={14} />
            {assignedOnly ? 'Show Full Dept Queue' : 'Show My Assignments Only'}
          </button>

          <button onClick={fetchQueue} className="btn btn-secondary btn-sm">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid-4">
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Shield size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{total}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Queue Complaints</div>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{critical}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Critical / Emergency</div>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Clock size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{inProgress}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>In Progress</div>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{resolved}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Resolved</div>
          </div>
        </div>
      </div>

      {/* Complaints Queue */}
      <div>
        <h2 style={{ fontSize: '1.35rem', marginBottom: '1.25rem' }}>
          {assignedOnly ? 'My Assigned Complaints' : 'Department Active Complaints'}
        </h2>

        {isLoading ? (
          <LoadingSpinner message="Fetching officer dispatch queue..." />
        ) : error ? (
          <ErrorMessage message={error} onRetry={fetchQueue} />
        ) : complaints.length === 0 ? (
          <EmptyState
            title="Queue is Clear"
            message="There are no pending or open grievances in this queue right now."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {complaints.map((c) => (
              <ComplaintCard key={c.id} complaint={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
