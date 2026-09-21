import React from 'react';
import { ComplaintHistory } from '../types';
import { StatusBadge } from './StatusBadge';
import { CheckCircle2, Clock, User, MessageSquare } from 'lucide-react';

interface TimelineViewProps {
  history: ComplaintHistory[];
  currentStatus: string;
}

export const TimelineView: React.FC<TimelineViewProps> = ({ history, currentStatus }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <h4 style={{ fontSize: '1rem', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Clock size={16} color="#3b82f6" /> Audit Timeline & History
      </h4>

      {history.length === 0 ? (
        <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>No status changes recorded yet.</p>
      ) : (
        <div style={{ position: 'relative', paddingLeft: '1.5rem', borderLeft: '2px solid var(--border-color)' }}>
          {history.map((item, idx) => {
            const isLatest = idx === 0;
            const dateStr = new Date(item.created_at).toLocaleString('en-IN', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });

            return (
              <div
                key={item.id}
                style={{
                  position: 'relative',
                  marginBottom: '1.5rem',
                  paddingLeft: '0.75rem',
                }}
              >
                {/* Node indicator dot */}
                <div
                  style={{
                    position: 'absolute',
                    left: '-2.15rem',
                    top: '0.15rem',
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    background: isLatest ? '#3b82f6' : '#64748b',
                    border: '3px solid var(--bg-primary)',
                    boxShadow: isLatest ? '0 0 10px #3b82f6' : 'none',
                  }}
                />

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <StatusBadge status={item.new_status} />
                    {item.previous_status && item.previous_status !== item.new_status && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        (from {item.previous_status})
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{dateStr}</span>
                </div>

                {item.note && (
                  <div
                    style={{
                      fontSize: '0.85rem',
                      color: 'var(--text-muted)',
                      background: 'rgba(15, 23, 42, 0.6)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: 'var(--radius-sm)',
                      marginTop: '0.35rem',
                      border: '1px solid var(--border-color)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.4rem',
                    }}
                  >
                    <MessageSquare size={13} style={{ marginTop: '0.2rem', flexShrink: 0 }} />
                    <span>{item.note}</span>
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.3rem' }}>
                  <User size={12} />
                  <span>By: {item.changed_by_name || 'System'}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
