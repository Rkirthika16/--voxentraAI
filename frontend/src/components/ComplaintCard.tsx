import React from 'react';
import { Link } from 'react-router-dom';
import { Complaint } from '../types';
import { StatusBadge } from './StatusBadge';
import { PriorityBadge } from './PriorityBadge';
import { MapPin, Calendar, Building2, ChevronRight, MessageSquare } from 'lucide-react';

interface ComplaintCardProps {
  complaint: Complaint;
}

export const ComplaintCard: React.FC<ComplaintCardProps> = ({ complaint }) => {
  const formattedDate = new Date(complaint.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <span style={{ fontWeight: 700, color: 'var(--color-primary)', fontSize: '0.95rem' }}>
            {complaint.complaint_number}
          </span>
          <span
            style={{
              fontSize: '0.75rem',
              background: 'rgba(148, 163, 184, 0.1)',
              padding: '0.15rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-muted)',
            }}
          >
            {complaint.category}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <PriorityBadge priority={complaint.priority} />
          <StatusBadge status={complaint.status} />
        </div>
      </div>

      <div>
        <h4 style={{ fontSize: '1.05rem', marginBottom: '0.35rem', color: 'var(--text-main)' }}>
          {complaint.title || 'Civic Issue'}
        </h4>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: '1.4', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {complaint.description}
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-color)', fontSize: '0.8rem', color: 'var(--text-dim)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {complaint.location && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-muted)' }}>
              <MapPin size={13} color="#38bdf8" />
              <span>{complaint.location}</span>
            </div>
          )}
          {complaint.department_name && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-muted)' }}>
              <Building2 size={13} color="#a78bfa" />
              <span>{complaint.department_name}</span>
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <Calendar size={13} />
            <span>{formattedDate}</span>
          </div>
        </div>

        <Link
          to={`/complaints/${complaint.complaint_number || complaint.id}`}
          className="btn btn-secondary btn-sm"
          style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem', color: 'var(--color-primary)' }}
        >
          View Details <ChevronRight size={14} />
        </Link>
      </div>
    </div>
  );
};
