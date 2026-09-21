import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextComplaint } from './TextComplaint';
import { VoiceComplaint } from './VoiceComplaint';
import { FileText, Mic, Sparkles, Shield } from 'lucide-react';

export const SubmitComplaint: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'text' | 'voice'>('text');

  return (
    <div className="page-container animate-fade-in" style={{ maxWidth: '850px' }}>
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            background: 'rgba(59, 130, 246, 0.15)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: 'var(--radius-full)',
            padding: '0.3rem 0.9rem',
            fontSize: '0.8rem',
            fontWeight: 600,
            color: '#60a5fa',
            marginBottom: '0.75rem',
          }}
        >
          <Sparkles size={14} /> Tamil Nadu Citizen Redressal
        </div>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.4rem' }}>Register Public Grievance</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          Submit your municipal grievance in Tamil, English, or Tanglish. Our AI analyzes and routes it instantly.
        </p>
      </div>

      {/* Tab Switcher */}
      <div
        style={{
          display: 'flex',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
          padding: '0.35rem',
          marginBottom: '2rem',
          gap: '0.5rem',
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab('text')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            padding: '0.75rem',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            background: activeTab === 'text' ? 'var(--color-primary)' : 'transparent',
            color: activeTab === 'text' ? '#ffffff' : 'var(--text-muted)',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          <FileText size={18} /> Type Text Complaint
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('voice')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            padding: '0.75rem',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            background: activeTab === 'voice' ? 'var(--color-primary)' : 'transparent',
            color: activeTab === 'voice' ? '#ffffff' : 'var(--text-muted)',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          <Mic size={18} /> Record Voice / Audio Upload
        </button>
      </div>

      {/* Tab View */}
      {activeTab === 'text' ? <TextComplaint /> : <VoiceComplaint />}
    </div>
  );
};
