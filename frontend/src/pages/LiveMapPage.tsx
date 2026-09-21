import React, { useState, useEffect } from 'react';
import { complaintsApi } from '../api/complaints';
import { Complaint } from '../types';
import { LiveComplaintMap, CATEGORY_CONFIG } from '../components/LiveComplaintMap';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Link } from 'react-router-dom';
import {
  MapPin,
  Layers,
  Sparkles,
  PhoneCall,
  Search,
  Building2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Filter
} from 'lucide-react';

export const LiveMapPage: React.FC = () => {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedComplaintId, setSelectedComplaintId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'critical'>('all');

  const fetchPins = async () => {
    setIsLoading(true);
    try {
      const data = await complaintsApi.getMapPins({ limit: 200 });
      setComplaints(data);
    } catch (err) {
      console.error('Failed to load map complaints:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPins();
  }, []);

  const criticalComplaints = complaints.filter((c) => c.priority === 'CRITICAL');

  return (
    <div className="page-container animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '1400px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: 'var(--radius-full)',
              padding: '0.3rem 0.85rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: '#38bdf8',
              marginBottom: '0.5rem',
            }}
          >
            <MapPin size={14} /> Real-Time Geographic Information System
          </div>
          <h1 style={{ fontSize: '1.85rem', margin: '0 0 0.25rem 0' }}>Tamil Nadu Live Grievance Map</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', margin: 0 }}>
            Geospatial visualization of civic complaints across Coimbatore, Chennai, Madurai, Salem, Trichy, and other districts
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <Link to="/toll-free" className="btn btn-primary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <PhoneCall size={15} /> Call Helpline 1913
          </Link>
          <button onClick={fetchPins} className="btn btn-secondary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <RefreshCw size={15} /> Refresh Pins
          </button>
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading live Tamil Nadu grievance coordinates..." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '1.5rem', alignItems: 'start' }}>
          {/* Main Map Canvas */}
          <div>
            <LiveComplaintMap
              complaints={complaints}
              height="680px"
              selectedComplaintId={selectedComplaintId}
              onSelectComplaint={(c) => setSelectedComplaintId(c.id)}
              showFilters={true}
            />
          </div>

          {/* Right Sidebar: Quick Inspection & Hotspots */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Quick Stats Summary Card */}
            <div className="glass-card" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Layers size={16} color="#60a5fa" /> GIS Summary
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem', marginBottom: '1rem' }}>
                <div style={{ background: 'var(--bg-input)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Geolocated</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#38bdf8' }}>{complaints.length}</div>
                </div>
                <div style={{ background: 'var(--bg-input)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Emergency Critical</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f87171' }}>{criticalComplaints.length}</div>
                </div>
              </div>

              {/* Department Legend Mini List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {Object.keys(CATEGORY_CONFIG)
                  .filter((k) => k !== 'Other')
                  .map((k) => {
                    const conf = CATEGORY_CONFIG[k];
                    const count = complaints.filter((c) => c.category === k).length;
                    return (
                      <div key={k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span>{conf.icon}</span>
                          <span style={{ color: 'var(--text-muted)' }}>{conf.label}</span>
                        </div>
                        <strong style={{ color: conf.color }}>{count}</strong>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Complaint Pin List */}
            <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', maxHeight: '420px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => setActiveTab('all')}
                    style={{
                      background: activeTab === 'all' ? 'var(--color-primary)' : 'transparent',
                      color: activeTab === 'all' ? '#ffffff' : 'var(--text-muted)',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.2rem 0.6rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    All ({complaints.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('critical')}
                    style={{
                      background: activeTab === 'critical' ? '#ef4444' : 'transparent',
                      color: activeTab === 'critical' ? '#ffffff' : 'var(--text-muted)',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.2rem 0.6rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Critical ({criticalComplaints.length})
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', overflowY: 'auto', paddingRight: '0.25rem' }}>
                {(activeTab === 'all' ? complaints : criticalComplaints).map((c) => {
                  const isSelected = selectedComplaintId === c.id;
                  const conf = CATEGORY_CONFIG[c.category] || CATEGORY_CONFIG['Other'];

                  return (
                    <div
                      key={c.id}
                      onClick={() => setSelectedComplaintId(c.id)}
                      style={{
                        background: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-input)',
                        border: `1px solid ${isSelected ? '#38bdf8' : 'var(--border-color)'}`,
                        borderRadius: 'var(--radius-sm)',
                        padding: '0.65rem 0.75rem',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8' }}>
                          {c.complaint_number}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: conf.color, fontWeight: 700 }}>
                          {conf.icon} {c.category}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '0.3rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {c.title}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                          📍 {c.location || 'Tamil Nadu'}
                        </span>
                        <span style={{ color: c.status === 'RESOLVED' ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                          {c.status.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
