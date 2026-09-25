import React from 'react';
import { CheckCircle2, Building, MessageSquare, PhoneCall, ArrowRight, FileText } from 'lucide-react';
import { Link } from 'react-router-dom';

interface CallCompletedProps {
  complaintNumber: string;
  department?: string;
  smsSent?: boolean;
  onNewCall: () => void;
}

export const CallCompleted: React.FC<CallCompletedProps> = ({
  complaintNumber,
  department,
  smsSent,
  onNewCall,
}) => {
  return (
    <div
      style={{
        padding: '2rem',
        borderRadius: '1rem',
        backgroundColor: '#ECFDF5',
        border: '2px solid #10B981',
        boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        gap: '1rem',
      }}
    >
      <div
        style={{
          width: '60px',
          height: '60px',
          borderRadius: '50%',
          backgroundColor: '#10B981',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#FFFFFF',
        }}
      >
        <CheckCircle2 size={36} />
      </div>

      <div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#065F46', margin: '0 0 0.25rem 0' }}>
          Complaint Successfully Registered!
        </h2>
        <p style={{ fontSize: '0.9rem', color: '#047857', margin: 0 }}>
          Your grievance has been officially submitted and assigned to municipal officers.
        </p>
      </div>

      <div
        style={{
          padding: '1rem 1.5rem',
          backgroundColor: '#FFFFFF',
          borderRadius: '0.75rem',
          border: '1px solid #A7F3D0',
          boxShadow: '0 2px 4px rgba(0,0,0,0.03)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          width: '100%',
          maxWidth: '380px',
        }}
      >
        <div style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 600 }}>OFFICIAL COMPLAINT ID</div>
        <div style={{ fontSize: '1.5rem', fontWeight: 900, color: '#1E40AF', letterSpacing: '0.05em' }}>
          {complaintNumber}
        </div>

        {department && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', fontSize: '0.85rem', color: '#334155', fontWeight: 600, marginTop: '0.25rem' }}>
            <Building size={15} className="text-indigo-600" />
            <span>Routed to: {department}</span>
          </div>
        )}

        {smsSent && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', fontSize: '0.8rem', color: '#059669', fontWeight: 500 }}>
            <MessageSquare size={14} />
            <span>SMS confirmation dispatched to your phone</span>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        <button
          type="button"
          onClick={onNewCall}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.75rem 1.25rem',
            borderRadius: '0.5rem',
            backgroundColor: '#2563EB',
            color: '#FFFFFF',
            fontWeight: 700,
            fontSize: '0.9rem',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <PhoneCall size={16} />
          <span>Start New Toll-Free Call</span>
        </button>

        <Link
          to={`/track`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.75rem 1.25rem',
            borderRadius: '0.5rem',
            backgroundColor: '#FFFFFF',
            color: '#1E293B',
            fontWeight: 700,
            fontSize: '0.9rem',
            border: '1px solid #CBD5E1',
            textDecoration: 'none',
          }}
        >
          <FileText size={16} />
          <span>Track Complaint Status</span>
          <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
};
