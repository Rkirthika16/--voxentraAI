import React, { useState } from 'react';
import { complaintsApi } from '../api/complaints';
import { Complaint } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { PriorityBadge } from '../components/PriorityBadge';
import { TimelineView } from '../components/TimelineView';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { Search, MapPin, Building2, Calendar, Shield, AlertCircle } from 'lucide-react';

export const ComplaintTracking: React.FC = () => {
  const [identifier, setIdentifier] = useState('');
  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTrack = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim()) return;

    setIsLoading(true);
    setError(null);
    setComplaint(null);

    try {
      const data = await complaintsApi.getComplaintDetails(identifier.trim());
      setComplaint(data);
    } catch (err: any) {
      setError(
        err.response?.status === 404
          ? `Grievance #${identifier} was not found. Please verify your tracking number.`
          : err.response?.data?.detail || 'Failed to retrieve complaint details.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="page-container animate-fade-in" style={{ maxWidth: '850px' }}>
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.85rem', marginBottom: '0.4rem' }}>Public Grievance Tracker</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          Enter your unique complaint tracking number (e.g. <span style={{ color: 'var(--color-primary)' }}>VOX-2026-0001</span>) to view real-time resolution status.
        </p>
      </div>

      {/* Search Input Bar */}
      <div className="glass-card" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <form onSubmit={handleTrack} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: '240px' }}>
            <input
              type="text"
              required
              className="form-input"
              placeholder="e.g. VOX-2026-0001 or 1"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              style={{ paddingLeft: '2.5rem' }}
            />
            <Search size={16} color="#64748b" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
          </div>

          <button type="submit" className="btn btn-primary" disabled={isLoading}>
            {isLoading ? 'Searching...' : 'Track Status'}
          </button>
        </form>
      </div>

      {isLoading && <LoadingSpinner message="Querying municipal records..." />}

      {error && <ErrorMessage message={error} />}

      {complaint && (
        <div className="glass-card animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-primary)' }}>
                  {complaint.complaint_number}
                </span>
                <span style={{ fontSize: '0.8rem', background: 'var(--bg-input)', padding: '0.2rem 0.5rem', borderRadius: 'var(--radius-sm)', color: 'var(--text-muted)' }}>
                  {complaint.category}
                </span>
              </div>
              <h3 style={{ fontSize: '1.15rem', color: 'var(--text-main)' }}>{complaint.title}</h3>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <PriorityBadge priority={complaint.priority} />
              <StatusBadge status={complaint.status} />
            </div>
          </div>

          <div style={{ background: 'var(--bg-input)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', display: 'block', marginBottom: '0.4rem' }}>
              Complaint Description
            </span>
            <p style={{ color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: '1.5' }}>
              {complaint.description}
            </p>
          </div>

          <div className="grid-2">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.85rem' }}>
              <Building2 size={16} color="#a78bfa" />
              <div>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Department</span>
                <strong>{complaint.department_name || 'General Administration'}</strong>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.85rem' }}>
              <MapPin size={16} color="#38bdf8" />
              <div>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Location</span>
                <strong>{complaint.location || 'Municipal Area'}</strong>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div style={{ marginTop: '1rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
            <TimelineView history={complaint.history || []} currentStatus={complaint.status} />
          </div>
        </div>
      )}
    </div>
  );
};
