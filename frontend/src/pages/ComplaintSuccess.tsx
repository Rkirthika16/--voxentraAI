import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Complaint } from '../types';
import { CheckCircle2, Copy, Check, Search, LayoutDashboard, Building2, Calendar, Shield } from 'lucide-react';

interface ComplaintSuccessProps {
  complaint: Complaint;
}

export const ComplaintSuccess: React.FC<ComplaintSuccessProps> = ({ complaint }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(complaint.complaint_number);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formattedDate = new Date(complaint.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="glass-card animate-fade-in" style={{ padding: '3rem 2rem', textAlign: 'center', maxWidth: '650px', margin: '0 auto' }}>
      <div
        style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 1.25rem',
          boxShadow: '0 0 25px rgba(16, 185, 129, 0.3)',
        }}
      >
        <CheckCircle2 size={36} />
      </div>

      <h2 style={{ fontSize: '1.85rem', marginBottom: '0.4rem' }}>Grievance Registered Successfully!</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '1.75rem' }}>
        Your complaint has been logged into the Tamil Nadu civic database and routed to the department.
      </p>

      {/* Tracking Number Card */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
          padding: '1.5rem',
          marginBottom: '2rem',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '0.75rem',
        }}
      >
        <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Official Grievance Tracking Number
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--color-primary)', letterSpacing: '0.04em' }}>
            {complaint.complaint_number}
          </span>
          <button
            onClick={handleCopy}
            className="btn btn-secondary btn-sm"
            title="Copy Tracking ID"
            style={{ padding: '0.4rem 0.6rem' }}
          >
            {copied ? <Check size={16} color="#10b981" /> : <Copy size={16} />}
          </button>
        </div>
      </div>

      {/* Summary Info */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '1rem',
          textAlign: 'left',
          fontSize: '0.875rem',
          marginBottom: '2rem',
          background: 'var(--bg-input)',
          padding: '1.25rem',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <div>
          <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.75rem' }}>Assigned Department</span>
          <strong style={{ color: 'var(--text-main)' }}>{complaint.department_name || 'General Administration'}</strong>
        </div>
        <div>
          <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.75rem' }}>Priority Level</span>
          <strong style={{ color: 'var(--text-main)' }}>{complaint.priority}</strong>
        </div>
        <div>
          <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.75rem' }}>Submission Time</span>
          <span>{formattedDate}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.75rem' }}>Current Status</span>
          <span style={{ color: '#38bdf8', fontWeight: 600 }}>SUBMITTED</span>
        </div>
      </div>

      {/* Action CTA Buttons */}
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
        <Link to={`/complaints/${complaint.complaint_number}`} className="btn btn-primary">
          <Search size={16} /> Track Grievance Status
        </Link>
        <Link to="/dashboard" className="btn btn-secondary">
          <LayoutDashboard size={16} /> Go to Dashboard
        </Link>
      </div>
    </div>
  );
};
