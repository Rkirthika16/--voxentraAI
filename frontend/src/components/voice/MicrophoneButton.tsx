import React from 'react';
import { Mic, MicOff, Square, Play, RotateCcw } from 'lucide-react';

interface MicrophoneButtonProps {
  isRecording: boolean;
  isProcessing: boolean;
  onToggleRecord: () => void;
  onCancel?: () => void;
  disabled?: boolean;
}

export const MicrophoneButton: React.FC<MicrophoneButtonProps> = ({
  isRecording,
  isProcessing,
  onToggleRecord,
  onCancel,
  disabled
}) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1.25rem', marginTop: '1rem' }}>
      <button
        type="button"
        onClick={onToggleRecord}
        disabled={disabled || isProcessing}
        style={{
          width: '76px',
          height: '76px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: isRecording
            ? 'linear-gradient(135deg, #ef4444, #dc2626)'
            : 'linear-gradient(135deg, #6366f1, #4f46e5)',
          color: '#ffffff',
          border: 'none',
          boxShadow: isRecording
            ? '0 0 35px rgba(239, 68, 68, 0.6)'
            : '0 0 25px rgba(99, 102, 241, 0.4)',
          cursor: disabled || isProcessing ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s ease',
          transform: isRecording ? 'scale(1.08)' : 'scale(1)',
        }}
        title={isRecording ? 'Click to Stop Speaking' : 'Click to Speak'}
      >
        {isRecording ? (
          <Square className="w-7 h-7 fill-white" />
        ) : (
          <Mic className="w-8 h-8" />
        )}
      </button>

      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: '0.6rem 1rem',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-secondary)',
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem'
          }}
          title="Reset conversation"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset</span>
        </button>
      )}
    </div>
  );
};
