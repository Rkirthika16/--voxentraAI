import React from 'react';
import { ComplaintStatus } from '../types';

interface StatusBadgeProps {
  status: ComplaintStatus | string;
}

const statusLabels: Record<string, string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
  REJECTED: 'Rejected',
  REOPENED: 'Reopened',
  OVERDUE: 'Overdue SLA',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normStatus = (status || 'SUBMITTED').toUpperCase();
  const label = statusLabels[normStatus] || normStatus;
  const badgeClass = `badge badge-${normStatus.toLowerCase()}`;

  return <span className={badgeClass}>{label}</span>;
};
