import React from 'react';
import { Languages, Radio } from 'lucide-react';
import { formatLanguageDisplay } from '../../utils/languageDetect';

interface LanguageIndicatorProps {
  language: string;
  confidence?: number;
}

export const LanguageIndicator: React.FC<LanguageIndicatorProps> = ({ language, confidence }) => {
  const getBadgeColor = (lang: string) => {
    const norm = (lang || '').toLowerCase().trim();
    if (norm === 'tamil' || norm === 'ta' || norm === 'ta-in') {
      return { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B', label: 'தமிழ் (Tamil)', isListening: false };
    }
    if (norm === 'english' || norm === 'en' || norm === 'en-in') {
      return { bg: '#EFF6FF', text: '#1E40AF', border: '#3B82F6', label: 'English', isListening: false };
    }
    if (norm === 'tanglish') {
      return { bg: '#F3E8FF', text: '#6B21A8', border: '#A855F7', label: 'Tanglish (தமிழ் + Eng)', isListening: false };
    }
    if (!norm || norm === 'auto' || norm.includes('auto') || norm.includes('detect')) {
      return { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B', label: 'தமிழ் (Tamil)', isListening: false };
    }
    return {
      bg: '#FEF3C7',
      text: '#92400E',
      border: '#F59E0B',
      label: formatLanguageDisplay(lang),
      isListening: false,
    };
  };

  const badge = getBadgeColor(language);

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.45rem',
        padding: '0.35rem 0.8rem',
        borderRadius: '9999px',
        backgroundColor: badge.bg,
        color: badge.text,
        border: `1px solid ${badge.border}`,
        fontSize: '0.85rem',
        fontWeight: 700,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}
    >
      {badge.isListening ? (
        <Radio size={14} className="animate-pulse" style={{ color: '#2563EB' }} />
      ) : (
        <Languages size={15} />
      )}
      <span>{badge.label}</span>
      {confidence !== undefined && confidence > 0 && !badge.isListening && (
        <span style={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 600 }}>
          ({Math.round(confidence * 100)}%)
        </span>
      )}
    </div>
  );
};
