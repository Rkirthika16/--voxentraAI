import React from 'react';
import { Mic, Volume2, Sparkles, AlertCircle, CheckCircle2, Clock, Check } from 'lucide-react';

export type VoiceState =
  | 'IDLE'
  | 'LISTENING'
  | 'PROCESSING'
  | 'AI_RESPONDING'
  | 'SPEAKING'
  | 'WAITING_FOR_USER'
  | 'CONFIRMING'
  | 'COMPLETED'
  | 'ERROR';

interface VoiceStatusProps {
  state: VoiceState;
  language?: string;
  category?: string;
  location?: string;
}

export const VoiceStatus: React.FC<VoiceStatusProps> = ({ state, language, category, location }) => {
  const getBadgeConfig = () => {
    switch (state) {
      case 'LISTENING':
        return {
          label: 'Listening to Citizen...',
          color: '#ef4444',
          bg: 'rgba(239, 68, 68, 0.15)',
          border: 'rgba(239, 68, 68, 0.3)',
          icon: <Mic className="w-4 h-4 animate-pulse" />
        };
      case 'PROCESSING':
        return {
          label: 'AI Reasoning & Language Detection...',
          color: '#3b82f6',
          bg: 'rgba(59, 130, 246, 0.15)',
          border: 'rgba(59, 130, 246, 0.3)',
          icon: <Sparkles className="w-4 h-4 animate-spin" />
        };
      case 'SPEAKING':
      case 'AI_RESPONDING':
        return {
          label: 'AI Speaking...',
          color: '#10b981',
          bg: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.3)',
          icon: <Volume2 className="w-4 h-4 animate-bounce" />
        };
      case 'CONFIRMING':
        return {
          label: 'Awaiting Citizen Confirmation',
          color: '#f59e0b',
          bg: 'rgba(245, 158, 11, 0.15)',
          border: 'rgba(245, 158, 11, 0.3)',
          icon: <AlertCircle className="w-4 h-4" />
        };
      case 'COMPLETED':
        return {
          label: 'Grievance Registered Successfully',
          color: '#10b981',
          bg: 'rgba(16, 185, 129, 0.2)',
          border: 'rgba(16, 185, 129, 0.4)',
          icon: <CheckCircle2 className="w-4 h-4" />
        };
      case 'ERROR':
        return {
          label: 'Voice Recognition Offline / Error',
          color: '#f43f5e',
          bg: 'rgba(244, 63, 94, 0.15)',
          border: 'rgba(244, 63, 94, 0.3)',
          icon: <AlertCircle className="w-4 h-4" />
        };
      default:
        return {
          label: 'You can speak now (Tamil / English / Tanglish)',
          color: '#a855f7',
          bg: 'rgba(168, 85, 247, 0.15)',
          border: 'rgba(168, 85, 247, 0.3)',
          icon: <Clock className="w-4 h-4" />
        };
    }
  };

  const badge = getBadgeConfig();

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.45rem 1rem',
          borderRadius: '9999px',
          background: badge.bg,
          border: `1px solid ${badge.border}`,
          color: badge.color,
          fontSize: '0.875rem',
          fontWeight: 600,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)'
        }}
      >
        {badge.icon}
        <span>{badge.label}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        {language && (
          <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: '4px', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
            🌐 {language}
          </span>
        )}
        {category && (
          <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', color: '#60a5fa' }}>
            📁 {category}
          </span>
        )}
        {location && (
          <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#34d399' }}>
            📍 {location}
          </span>
        )}
      </div>
    </div>
  );
};
