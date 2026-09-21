import React from 'react';
import { ComplaintPriority } from '../types';
import { AlertCircle, AlertTriangle, Info, Clock } from 'lucide-react';

interface PriorityBadgeProps {
  priority: ComplaintPriority | string;
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority }) => {
  const normPri = (priority || 'MEDIUM').toUpperCase();

  switch (normPri) {
    case 'CRITICAL':
      return (
        <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid #ef4444' }}>
          <AlertCircle size={12} /> Critical / Emergency
        </span>
      );
    case 'HIGH':
      return (
        <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', border: '1px solid #f59e0b' }}>
          <AlertTriangle size={12} /> High Priority
        </span>
      );
    case 'MEDIUM':
      return (
        <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', border: '1px solid #3b82f6' }}>
          <Info size={12} /> Medium Priority
        </span>
      );
    case 'LOW':
      return (
        <span className="badge" style={{ background: 'rgba(148, 163, 184, 0.2)', color: '#cbd5e1', border: '1px solid #64748b' }}>
          <Clock size={12} /> Low Priority
        </span>
      );
    default:
      return <span className="badge">{normPri}</span>;
  }
};
