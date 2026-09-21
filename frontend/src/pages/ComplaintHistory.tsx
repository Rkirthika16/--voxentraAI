import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { complaintsApi } from '../api/complaints';
import { Complaint, ComplaintStatus, ComplaintPriority } from '../types';
import { ComplaintCard } from '../components/ComplaintCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import { Search, Filter, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';

export const ComplaintHistory: React.FC = () => {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);

  const fetchComplaints = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params: any = {
        page,
        page_size: 15,
      };
      if (statusFilter) params.status = statusFilter as ComplaintStatus;
      if (categoryFilter) params.category = categoryFilter;
      if (priorityFilter) params.priority = priorityFilter as ComplaintPriority;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const data = await complaintsApi.listComplaints(params);
      setComplaints(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch complaints history.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaints();
  }, [statusFilter, categoryFilter, priorityFilter, page]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchComplaints();
  };

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.85rem', marginBottom: '0.35rem' }}>Grievance Records</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            {user?.role === 'CITIZEN' ? 'All complaints registered under your citizen profile' : 'Municipal complaint directory'}
          </p>
        </div>

        <button onClick={fetchComplaints} className="btn btn-secondary btn-sm">
          <RefreshCw size={14} /> Refresh Records
        </button>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="glass-card" style={{ padding: '1.25rem' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Search Grievances</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-input"
                placeholder="ID, keyword, landmark..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingLeft: '2.25rem', fontSize: '0.85rem' }}
              />
              <Search size={14} color="#64748b" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Status</label>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              style={{ fontSize: '0.85rem' }}
            >
              <option value="">All Statuses</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="ASSIGNED">Assigned</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="RESOLVED">Resolved</option>
              <option value="REJECTED">Rejected</option>
              <option value="REOPENED">Reopened</option>
              <option value="OVERDUE">Overdue SLA</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Category</label>
            <select
              className="form-select"
              value={categoryFilter}
              onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
              style={{ fontSize: '0.85rem' }}
            >
              <option value="">All Categories</option>
              <option value="Water">Water Supply</option>
              <option value="Electricity">Electricity & Power</option>
              <option value="Roads">Roads & Transport</option>
              <option value="Sanitation/Garbage">Sanitation</option>
              <option value="Drainage">Drainage</option>
              <option value="Streetlights">Streetlights</option>
              <option value="Public Safety">Public Safety</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" style={{ fontSize: '0.75rem' }}>Priority</label>
            <select
              className="form-select"
              value={priorityFilter}
              onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }}
              style={{ fontSize: '0.85rem' }}
            >
              <option value="">All Priorities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          <button type="submit" className="btn btn-primary" style={{ height: '42px', fontSize: '0.85rem' }}>
            <Filter size={14} /> Filter
          </button>
        </form>
      </div>

      {/* Complaint List Display */}
      {isLoading ? (
        <LoadingSpinner message="Loading complaint records..." />
      ) : error ? (
        <ErrorMessage message={error} onRetry={fetchComplaints} />
      ) : complaints.length === 0 ? (
        <EmptyState
          title="No Matching Grievances"
          message="Try clearing your filters or search keywords to see all records."
          actionText="Clear Filters"
          onAction={() => {
            setStatusFilter('');
            setCategoryFilter('');
            setPriorityFilter('');
            setSearchQuery('');
            setPage(1);
          }}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {complaints.map((c) => (
            <ComplaintCard key={c.id} complaint={c} />
          ))}

          {/* Pagination Toolbar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn btn-secondary btn-sm"
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={complaints.length < 15}
              className="btn btn-secondary btn-sm"
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
