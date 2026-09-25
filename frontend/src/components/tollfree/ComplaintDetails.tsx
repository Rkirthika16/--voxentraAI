import React from 'react';
import {
  FileText,
  MapPin,
  Clock,
  Building,
  AlertTriangle,
  Users,
  Activity,
  Layers,
  Sparkles
} from 'lucide-react';
import { TollFreeMemory } from '../../api/tollfree';

interface ComplaintDetailsProps {
  memory: TollFreeMemory;
}

export const ComplaintDetails: React.FC<ComplaintDetailsProps> = ({ memory }) => {
  const getPriorityBadge = (priority: string | null) => {
    switch (priority) {
      case 'CRITICAL':
        return { bg: '#FEF2F2', text: '#991B1B', border: '#EF4444' };
      case 'HIGH':
        return { bg: '#FFF7ED', text: '#C2410C', border: '#F97316' };
      case 'MEDIUM':
        return { bg: '#FFFBEB', text: '#B45309', border: '#F59E0B' };
      case 'LOW':
        return { bg: '#F0FDF4', text: '#166534', border: '#22C55E' };
      default:
        return { bg: '#F1F5F9', text: '#475569', border: '#94A3B8' };
    }
  };

  const priorityStyle = getPriorityBadge(memory.priority);

  const memoryFields = [
    {
      label: 'Category',
      value: memory.category,
      icon: <Layers size={14} className="text-blue-500" />,
      missing: !memory.category,
    },
    {
      label: 'Specific Problem',
      value: memory.problem,
      icon: <FileText size={14} className="text-indigo-500" />,
      missing: !memory.problem,
    },
    {
      label: 'Location / Area',
      value: memory.location,
      icon: <MapPin size={14} className="text-red-500" />,
      missing: !memory.location,
      highlight: !!memory.location,
    },
    {
      label: 'Duration',
      value: memory.duration,
      icon: <Clock size={14} className="text-amber-500" />,
      missing: !memory.duration,
    },
    {
      label: 'Affected Scope',
      value: memory.affected_scope,
      icon: <Users size={14} className="text-teal-500" />,
      missing: !memory.affected_scope,
    },
    {
      label: 'Frequency',
      value: memory.frequency,
      icon: <Activity size={14} className="text-purple-500" />,
      missing: !memory.frequency,
    },
    {
      label: 'Department Routing',
      value: memory.department,
      icon: <Building size={14} className="text-emerald-500" />,
      missing: !memory.department,
    },
  ];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        padding: '1.25rem',
        backgroundColor: '#FFFFFF',
        borderRadius: '1rem',
        border: '1px solid #E2E8F0',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.95rem', color: '#1E293B' }}>
          <Sparkles size={16} className="text-indigo-600" />
          <span>Live Complaint Memory Context</span>
        </div>

        {memory.priority && (
          <span
            style={{
              padding: '0.2rem 0.6rem',
              borderRadius: '9999px',
              backgroundColor: priorityStyle.bg,
              color: priorityStyle.text,
              border: `1px solid ${priorityStyle.border}`,
              fontSize: '0.75rem',
              fontWeight: 700,
            }}
          >
            {memory.priority} PRIORITY
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
        {memoryFields.map((field, idx) => (
          <div
            key={idx}
            style={{
              padding: '0.65rem 0.85rem',
              borderRadius: '0.5rem',
              backgroundColor: field.missing ? '#F8FAFC' : '#F0FDF4',
              border: field.missing ? '1px dashed #CBD5E1' : '1px solid #BBF7D0',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.25rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: '#64748B', fontWeight: 600 }}>
              {field.icon}
              <span>{field.label}</span>
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: field.missing ? '#94A3B8' : '#0F172A', wordBreak: 'break-word' }}>
              {field.value || 'Waiting for details...'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
