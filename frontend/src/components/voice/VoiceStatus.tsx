import React from 'react';
import { Mic, Volume2, Sparkles, AlertCircle, CheckCircle2, Clock, PhoneOff, Globe, Brain, Radio } from 'lucide-react';

export type VoiceState =
  | 'IDLE'
  | 'AI_SPEAKING'
  | 'WAITING_FOR_CITIZEN'
  | 'WAITING_FOR_USER'
  | 'CITIZEN_SPEAKING'
  | 'LISTENING'
  | 'PROCESSING_AUDIO'
  | 'PROCESSING'
  | 'TRANSCRIBING'
  | 'DETECTING_LANGUAGE'
  | 'UNDERSTANDING'
  | 'GENERATING_RESPONSE'
  | 'AI_RESPONDING'
  | 'SPEAKING'
  | 'CONFIRMING'
  | 'CONFIRMED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'CALL_ENDED'
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
      case 'CITIZEN_SPEAKING':
      case 'LISTENING':
        return {
          label: '🔴 Listening...',
          color: '#ef4444',
          bg: 'rgba(239, 68, 68, 0.15)',
          border: 'rgba(239, 68, 68, 0.35)',
          icon: <Radio className="w-4 h-4 animate-pulse" />
        };
      case 'WAITING_FOR_CITIZEN':
      case 'WAITING_FOR_USER':
        return {
          label: '🎤 Your turn — Listening...',
          color: '#a855f7',
          bg: 'rgba(168, 85, 247, 0.15)',
          border: 'rgba(168, 85, 247, 0.35)',
          icon: <Mic className="w-4 h-4" />
        };
      case 'PROCESSING_AUDIO':
      case 'PROCESSING':
        return {
          label: '🧠 Processing...',
          color: '#3b82f6',
          bg: 'rgba(59, 130, 246, 0.15)',
          border: 'rgba(59, 130, 246, 0.35)',
          icon: <Brain className="w-4 h-4 animate-pulse" />
        };
      case 'TRANSCRIBING':
        return {
          label: '⏳ Transcribing Speech...',
          color: '#3b82f6',
          bg: 'rgba(59, 130, 246, 0.15)',
          border: 'rgba(59, 130, 246, 0.35)',
          icon: <Sparkles className="w-4 h-4 animate-spin" />
        };
      case 'DETECTING_LANGUAGE':
        return {
          label: '🌐 Detecting Language...',
          color: '#06b6d4',
          bg: 'rgba(6, 182, 212, 0.15)',
          border: 'rgba(6, 182, 212, 0.35)',
          icon: <Globe className="w-4 h-4 animate-spin" />
        };
      case 'UNDERSTANDING':
        return {
          label: '⏳ Understanding...',
          color: '#6366f1',
          bg: 'rgba(99, 102, 241, 0.15)',
          border: 'rgba(99, 102, 241, 0.35)',
          icon: <Brain className="w-4 h-4 animate-pulse" />
        };
      case 'GENERATING_RESPONSE':
      case 'AI_RESPONDING':
        return {
          label: '🔊 Responding...',
          color: '#10b981',
          bg: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.35)',
          icon: <Volume2 className="w-4 h-4 animate-bounce" />
        };
      case 'AI_SPEAKING':
      case 'SPEAKING':
        return {
          label: '🔊 AI Speaking...',
          color: '#10b981',
          bg: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.35)',
          icon: <Volume2 className="w-4 h-4 animate-bounce" />
        };
      case 'CONFIRMING':
        return {
          label: '⚠️ Awaiting Citizen Confirmation',
          color: '#f59e0b',
          bg: 'rgba(245, 158, 11, 0.15)',
          border: 'rgba(245, 158, 11, 0.35)',
          icon: <AlertCircle className="w-4 h-4" />
        };
      case 'CONFIRMED':
      case 'COMPLETED':
        return {
          label: '✅ Grievance Confirmed & Registered',
          color: '#10b981',
          bg: 'rgba(16, 185, 129, 0.2)',
          border: 'rgba(16, 185, 129, 0.45)',
          icon: <CheckCircle2 className="w-4 h-4" />
        };
      case 'CANCELLED':
        return {
          label: 'Session Cancelled',
          color: '#64748b',
          bg: 'rgba(100, 116, 139, 0.15)',
          border: 'rgba(100, 116, 139, 0.3)',
          icon: <Clock className="w-4 h-4" />
        };
      case 'CALL_ENDED':
        return {
          label: 'Call Ended',
          color: '#64748b',
          bg: 'rgba(100, 116, 139, 0.15)',
          border: 'rgba(100, 116, 139, 0.3)',
          icon: <PhoneOff className="w-4 h-4" />
        };
      case 'ERROR':
        return {
          label: 'Microphone Permission Required / Error',
          color: '#f43f5e',
          bg: 'rgba(244, 63, 94, 0.15)',
          border: 'rgba(244, 63, 94, 0.35)',
          icon: <AlertCircle className="w-4 h-4" />
        };
      default:
        return {
          label: 'Ready — Auto-Detecting Language',
          color: '#a855f7',
          bg: 'rgba(168, 85, 247, 0.15)',
          border: 'rgba(168, 85, 247, 0.35)',
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
