import React from 'react';
import { Languages, Globe2 } from 'lucide-react';

interface LanguageIndicatorProps {
  language: string;
  confidence?: number;
}

export const LanguageIndicator: React.FC<LanguageIndicatorProps> = ({ language, confidence }) => {
  const getBadgeColor = (lang: string) => {
    switch (lang.toLowerCase()) {
      case 'tamil':
      case 'ta':
        return { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B', label: 'தமிழ் (Tamil)' };
      case 'english':
      case 'en':
        return { bg: '#EFF6FF', text: '#1E40AF', border: '#3B82F6', label: 'English' };
      case 'tanglish':
        return { bg: '#F3E8FF', text: '#6B21A8', border: '#A855F7', label: 'Tanglish (தமிழ் + Eng)' };
      default:
        return { bg: '#F1F5F9', text: '#475569', border: '#94A3B8', label: 'Auto-Detecting' };
    }
  };

  const badge = getBadgeColor(language);

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.35rem 0.75rem',
        borderRadius: '9999px',
        backgroundColor: badge.bg,
        color: badge.text,
        border: `1px solid ${badge.border}`,
        fontSize: '0.85rem',
        fontWeight: 600,
        boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
      }}
    >
      <Languages size={15} />
      <span>{badge.label}</span>
      {confidence !== undefined && confidence > 0 && (
        <span style={{ opacity: 0.7, fontSize: '0.75rem', fontWeight: 500 }}>
          ({Math.round(confidence * 100)}%)
        </span>
      )}
    </div>
  );
};
