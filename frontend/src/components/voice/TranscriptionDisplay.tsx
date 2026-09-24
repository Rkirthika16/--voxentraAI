import React, { useState } from 'react';
import { Edit3, Check, Sparkles, Send } from 'lucide-react';

interface TranscriptionDisplayProps {
  originalText: string;
  normalizedText?: string;
  isProcessing: boolean;
  onEditSubmit?: (text: string) => void;
}

export const TranscriptionDisplay: React.FC<TranscriptionDisplayProps> = ({
  originalText,
  normalizedText,
  isProcessing,
  onEditSubmit
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(originalText);

  if (!originalText && !isProcessing) {
    return null;
  }

  const handleSaveEdit = () => {
    setIsEditing(false);
    if (onEditSubmit && editText.trim()) {
      onEditSubmit(editText.trim());
    }
  };

  return (
    <div
      style={{
        background: 'rgba(99, 102, 241, 0.05)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
        borderRadius: 'var(--radius-lg)',
        padding: '1rem 1.25rem',
        marginTop: '0.75rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#818cf8', fontSize: '0.8rem', fontWeight: 600 }}>
          <Sparkles className="w-3.5 h-3.5" />
          <span>LIVE TRANSCRIPTION</span>
        </div>

        {!isEditing && onEditSubmit && originalText && (
          <button
            type="button"
            onClick={() => {
              setEditText(originalText);
              setIsEditing(true);
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              fontSize: '0.75rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem'
            }}
          >
            <Edit3 className="w-3 h-3" />
            <span>Edit</span>
          </button>
        )}
      </div>

      {isEditing ? (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
          <input
            type="text"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit()}
            style={{
              flex: 1,
              padding: '0.5rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontSize: '0.9rem'
            }}
            autoFocus
          />
          <button
            type="button"
            onClick={handleSaveEdit}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--primary-color)',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.85rem'
            }}
          >
            <Send className="w-3.5 h-3.5" />
            <span>Submit</span>
          </button>
        </div>
      ) : (
        <div>
          <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: 500 }}>
            "{originalText}"
          </p>
          {normalizedText && normalizedText !== originalText && (
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Normalized: {normalizedText}
            </p>
          )}
        </div>
      )}
    </div>
  );
};
