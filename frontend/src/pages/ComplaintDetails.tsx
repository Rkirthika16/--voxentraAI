import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsApi } from '../api/complaints';
import { officersApi } from '../api/officers';
import { Complaint, ComplaintStatus, User } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { PriorityBadge } from '../components/PriorityBadge';
import { TimelineView } from '../components/TimelineView';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import {
  Building2,
  MapPin,
  Calendar,
  User as UserIcon,
  Sparkles,
  ArrowLeft,
  CheckCircle,
  Clock,
  Send,
  AlertTriangle,
  UserCheck
} from 'lucide-react';

export const ComplaintDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();

  const [complaint, setComplaint] = useState<Complaint | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Status update state
  const [newStatus, setNewStatus] = useState<ComplaintStatus>('IN_PROGRESS');
  const [statusNote, setStatusNote] = useState('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  // Assignment state
  const [officers, setOfficers] = useState<User[]>([]);
  const [selectedOfficerId, setSelectedOfficerId] = useState<number | ''>('');
  const [assignNotes, setAssignNotes] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);

  const fetchDetails = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await complaintsApi.getComplaintDetails(id);
      setComplaint(data);

      // If officer/admin, load officer list
      if (user && (user.role === 'OFFICER' || user.role === 'ADMIN')) {
        const offList = await officersApi.listOfficers(data.department_id);
        setOfficers(offList);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load complaint details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [id]);

  const handleStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!complaint) return;
    setIsUpdatingStatus(true);
    try {
      await complaintsApi.updateStatus(complaint.id, newStatus, statusNote.trim() || undefined);
      setStatusNote('');
      await fetchDetails();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Status update failed.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleAssignOfficer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!complaint || !selectedOfficerId) return;
    setIsAssigning(true);
    try {
      await officersApi.assignComplaint(complaint.id, Number(selectedOfficerId), assignNotes.trim() || undefined);
      setAssignNotes('');
      await fetchDetails();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Officer assignment failed.');
    } finally {
      setIsAssigning(false);
    }
  };

  const handleCitizenReopen = async () => {
    if (!complaint) return;
    const note = prompt('Please state why you are reopening this grievance:');
    if (!note) return;

    try {
      await complaintsApi.updateStatus(complaint.id, 'REOPENED' as ComplaintStatus, note);
      await fetchDetails();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to reopen complaint.');
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Fetching complaint record..." />;
  }

  if (error || !complaint) {
    return (
      <div className="page-container" style={{ maxWidth: '800px' }}>
        <ErrorMessage message={error || 'Complaint not found.'} onRetry={fetchDetails} />
        <Link to="/history" className="btn btn-secondary btn-sm" style={{ marginTop: '1rem' }}>
          <ArrowLeft size={16} /> Back to Records
        </Link>
      </div>
    );
  }

  const isOfficerOrAdmin = user && (user.role === 'OFFICER' || user.role === 'ADMIN');
  const isCitizenOwner = user && user.role === 'CITIZEN' && complaint.citizen_id === user.id;

  return (
    <div className="page-container animate-fade-in" style={{ maxWidth: '950px', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <Link to={user?.role === 'CITIZEN' ? '/dashboard' : '/history'} className="btn btn-secondary btn-sm">
          <ArrowLeft size={16} /> Back
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <PriorityBadge priority={complaint.priority} />
          <StatusBadge status={complaint.status} />
        </div>
      </div>

      {/* Main Grievance Details Card */}
      <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '2rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--color-primary)' }}>
              {complaint.complaint_number}
            </span>
            <span style={{ fontSize: '0.8rem', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-sm)' }}>
              {complaint.category}
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
              via {complaint.source}
            </span>
          </div>

          <h2 style={{ fontSize: '1.35rem', color: 'var(--text-main)', marginBottom: '0.75rem' }}>
            {complaint.title}
          </h2>

          <div style={{ background: 'var(--bg-input)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', display: 'block', marginBottom: '0.4rem' }}>
              Citizen Description
            </span>
            <p style={{ color: 'var(--text-main)', fontSize: '0.95rem', lineHeight: '1.5' }}>
              {complaint.description}
            </p>
          </div>
        </div>

        {/* Location & Department Row */}
        <div className="grid-3" style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
          <div>
            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Department</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.2rem' }}>
              <Building2 size={16} color="#a78bfa" />
              <strong>{complaint.department_name || 'General Administration'}</strong>
            </div>
          </div>

          <div>
            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Location / Landmark</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.2rem' }}>
              <MapPin size={16} color="#38bdf8" />
              <strong>{complaint.location || 'Municipal Zone'}</strong>
            </div>
          </div>

          <div>
            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', display: 'block' }}>Assigned Officer</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.2rem' }}>
              <UserIcon size={16} color="#34d399" />
              <strong>{complaint.assigned_officer_name || 'Pending Assignment'}</strong>
            </div>
          </div>
        </div>

        {/* AI Metadata Inspection */}
        {complaint.ai_metadata && (
          <div style={{ background: 'rgba(59, 130, 246, 0.06)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '1rem 1.25rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#60a5fa', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.4rem' }}>
              <Sparkles size={15} /> AI Processing Diagnostics
            </div>
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              <span>Method: <strong>{complaint.ai_metadata.analysis_method || 'deterministic_fallback'}</strong></span>
              <span>Language: <strong>{complaint.language}</strong></span>
              <span>Citizen Verified: <strong>{complaint.citizen_confirmed ? 'Yes' : 'No'}</strong></span>
            </div>
          </div>
        )}

        {/* Citizen Reopen Option */}
        {isCitizenOwner && ['RESOLVED', 'REJECTED'].includes(complaint.status) && (
          <div style={{ background: 'rgba(236, 72, 153, 0.1)', border: '1px solid rgba(236, 72, 153, 0.3)', padding: '1rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h4 style={{ color: '#f472b6', fontSize: '0.95rem' }}>Dissatisfied with the Resolution?</h4>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>You may request reopening of this grievance with additional remarks.</p>
            </div>
            <button onClick={handleCitizenReopen} className="btn btn-secondary btn-sm" style={{ borderColor: '#f472b6', color: '#f472b6' }}>
              Reopen Grievance
            </button>
          </div>
        )}
      </div>

      {/* Officer & Admin Status Management Panel */}
      {isOfficerOrAdmin && (
        <div className="grid-2">
          {/* Status Update Card */}
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle size={18} color="#3b82f6" /> Update Grievance Status
            </h3>
            <form onSubmit={handleStatusUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">New Status</label>
                <select
                  className="form-select"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value as ComplaintStatus)}
                >
                  <option value="UNDER_REVIEW">UNDER_REVIEW (Inspection Scheduled)</option>
                  <option value="ASSIGNED">ASSIGNED (Assigned to Staff)</option>
                  <option value="IN_PROGRESS">IN_PROGRESS (Work Underway)</option>
                  <option value="RESOLVED">RESOLVED (Action Completed)</option>
                  <option value="REJECTED">REJECTED (Invalid / Duplicate)</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Resolution / Action Note *</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  required
                  placeholder="e.g. Pipeline repaired by Field Unit 4, tested flow..."
                  value={statusNote}
                  onChange={(e) => setStatusNote(e.target.value)}
                />
              </div>

              <button type="submit" className="btn btn-primary btn-sm" disabled={isUpdatingStatus}>
                {isUpdatingStatus ? 'Updating...' : 'Save Status Change'}
              </button>
            </form>
          </div>

          {/* Officer Assignment Card */}
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <UserCheck size={18} color="#34d399" /> Assign Field Officer
            </h3>
            <form onSubmit={handleAssignOfficer} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Select Officer</label>
                <select
                  className="form-select"
                  required
                  value={selectedOfficerId}
                  onChange={(e) => setSelectedOfficerId(e.target.value ? Number(e.target.value) : '')}
                >
                  <option value="">-- Choose Field Officer --</option>
                  {officers.map((off) => (
                    <option key={off.id} value={off.id}>
                      {off.full_name} ({off.email})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Instructions / Task Notes</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Inspect site by 4 PM today"
                  value={assignNotes}
                  onChange={(e) => setAssignNotes(e.target.value)}
                />
              </div>

              <button type="submit" className="btn btn-secondary btn-sm" disabled={isAssigning || !selectedOfficerId}>
                {isAssigning ? 'Assigning...' : 'Assign to Officer'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* History Timeline */}
      <div className="glass-card" style={{ padding: '2rem' }}>
        <TimelineView history={complaint.history || []} currentStatus={complaint.status} />
      </div>
    </div>
  );
};
