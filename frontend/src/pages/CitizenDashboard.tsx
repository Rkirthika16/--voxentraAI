import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsApi } from '../api/complaints';
import { Complaint } from '../types';
import { ComplaintCard } from '../components/ComplaintCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { EmptyState } from '../components/EmptyState';
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  PlusCircle,
  Mic,
  Search,
  ArrowRight,
  Sparkles
} from 'lucide-react';

export const CitizenDashboard: React.FC = () => {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchComplaints = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await complaintsApi.getMyComplaints();
      setComplaints(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load your complaints.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaints();
  }, []);

  const total = complaints.length;
  const pending = complaints.filter((c) => ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED'].includes(c.status)).length;
  const inProgress = complaints.filter((c) => c.status === 'IN_PROGRESS').length;
  const resolved = complaints.filter((c) => c.status === 'RESOLVED').length;

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Welcome Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.85rem', marginBottom: '0.35rem' }}>
            Welcome back, {user?.full_name}
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Track your registered grievances and submit new municipal reports across Tamil Nadu.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <Link
            to="/new-ivr"
            className="btn btn-primary btn-sm"
            style={{
              background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
              boxShadow: '0 0 15px rgba(37, 99, 235, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              fontWeight: 700,
            }}
          >
            <Sparkles size={16} /> 🎙️ Live Two-Way IVR
          </Link>
          <Link
            to="/assistant"
            className="btn btn-secondary btn-sm"
            style={{
              background: 'linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(109, 40, 217, 0.3))',
              borderColor: 'rgba(139, 92, 246, 0.4)',
              color: '#c084fc',
              fontWeight: 600,
            }}
          >
            <Sparkles size={16} /> AI Companion
          </Link>
          <Link to="/voice-complaint" className="btn btn-secondary btn-sm">
            <Mic size={16} /> Voice Report
          </Link>
          <Link to="/submit" className="btn btn-secondary btn-sm">
            <PlusCircle size={16} /> New Grievance
          </Link>
        </div>
      </div>

      {/* Interactive AI Assistant Banner */}
      <div
        className="glass-card"
        style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95))',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          padding: '1.25rem 1.75rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 15px rgba(59, 130, 246, 0.5)',
            }}
          >
            <Sparkles size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-main)' }}>
              Need Help? Talk to Voxentra AI Assistant
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Speak or ask questions in Tamil, English, or Tanglish — check status, report issues, or get helpline numbers.
            </div>
          </div>
        </div>

        <Link to="/assistant" className="btn btn-primary btn-sm">
          Launch Voice Companion <ArrowRight size={14} />
        </Link>
      </div>

      {/* Metrics Row */}
      <div className="grid-4">
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FileText size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{total}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Submitted</div>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Clock size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{pending}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Pending Review</div>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{inProgress}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>In Progress</div>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>{resolved}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Resolved</div>
          </div>
        </div>
      </div>

      {/* Complaints List Section */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <h2 style={{ fontSize: '1.35rem' }}>Your Recent Grievances</h2>
          {complaints.length > 0 && (
            <Link to="/history" style={{ color: 'var(--color-primary)', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'none' }}>
              View All History <ArrowRight size={15} />
            </Link>
          )}
        </div>

        {isLoading ? (
          <LoadingSpinner message="Fetching your grievances..." />
        ) : error ? (
          <ErrorMessage message={error} onRetry={fetchComplaints} />
        ) : complaints.length === 0 ? (
          <EmptyState
            title="No Grievances Submitted Yet"
            message="Have a civic issue such as a water leak, road pothole, or broken streetlight? Report it in seconds using voice or text."
            actionText="Submit Your First Grievance"
            onAction={() => window.location.href = '/submit'}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {complaints.slice(0, 5).map((complaint) => (
              <ComplaintCard key={complaint.id} complaint={complaint} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
